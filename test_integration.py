"""Le pipeline entier, de bout en bout, sans réseau.

Ajouté le 27/08/2026. Les 123 tests existants couvrent chaque pièce
séparément — et test_agent.py bouche `evaluate_symbol`, donc la stratégie, le
garde anti-fuite, les portes de risque et le dimensionnement n'étaient JAMAIS
traversés ensemble. Après une journée de correctifs répartis sur risk_gates,
agent, alpaca_cli, vol_strategy et hindsight_guard, c'est exactement là qu'un
défaut de câblage se cacherait : chaque pièce verte, l'assemblage cassé.

Seule la FRONTIÈRE est bouchée : les fonctions d'alpaca_cli qui parlent au CLI.
Tout ce qui est au-dessus tourne pour de vrai — daily_returns, _hv_series,
score_hv_window, check_selection_leakage, today_regime, direction_tiebreak,
check_gates, le dimensionnement, la journalisation.

Un garde-fou dans setUp fait échouer bruyamment tout test qui atteindrait
`alpaca_cli.run` — c'est-à-dire le réseau.
"""

from __future__ import annotations

import contextlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

os.environ.setdefault("ALPACA_API_KEY", "cle-de-test")
os.environ.setdefault("ALPACA_SECRET_KEY", "secret-de-test")
os.environ["ALPACA_LIVE_TRADE"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parent))

import agent  # noqa: E402
import alpaca_cli  # noqa: E402
import config  # noqa: E402
import decision_log  # noqa: E402
import risk_gates  # noqa: E402
import vol_strategy  # noqa: E402


def serie(n, graine, amplitude=1000, calme_a_la_fin=0):
    """Série de prix déterministe. Pas de Math.random : suite congruentielle,
    pour que l'échec d'un test soit reproductible à l'identique.

    `calme_a_la_fin` réduit l'amplitude sur les N derniers jours — c'est ce qui
    fabrique un régime de volatilité BASSE, donc un rang HV sous le seuil, donc
    un symbole négociable. Sans ce levier, un test « l'agent entre en position »
    dépendrait du hasard de la graine.
    """
    prix, out, x = 100.0, [], graine
    for i in range(n):
        x = (1103515245 * x + 12345) % (2 ** 31)
        amp = amplitude
        if calme_a_la_fin and i >= n - calme_a_la_fin:
            amp = max(1, amplitude // 40)
        prix *= 1.0 + ((x % (2 * amp + 1)) - amp) / 100000.0
        out.append(vol_strategy.Bar(close=prix))
    return out


class BaseIntegration(unittest.TestCase):
    EQUITE = 100000.0
    N_BARRES = vol_strategy.MIN_TRADING_DAYS_FOR_SWEEP + 20

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hindsight-integ-"))
        self._sauve = {nom: getattr(alpaca_cli, nom) for nom in (
            "run", "get_clock", "get_daily_bars", "list_positions",
            "list_open_option_positions", "get_account", "get_option_ask_price",
            "find_near_the_money_contract", "submit_paper_option_order",
            "close_position")}
        self._state, self._log, self._halt = (
            risk_gates.STATE_FILE, decision_log.LOG_FILE, risk_gates.HALT_FILE)
        self._req = config.require_credentials

        risk_gates.STATE_FILE = self.tmp / "state.json"
        decision_log.LOG_FILE = self.tmp / "decision_log.jsonl"
        risk_gates.HALT_FILE = self.tmp / "HALT"
        config.require_credentials = lambda: None

        def _interdit(*a, **k):
            raise AssertionError(
                "un test d'intégration a atteint alpaca_cli.run — donc le "
                "réseau. args=%r" % (a,))

        alpaca_cli.run = _interdit
        alpaca_cli.get_clock = lambda: {"is_open": True}
        alpaca_cli.get_account = lambda: {
            "id": "compte-integ", "equity": str(self.EQUITE),
            "portfolio_value": str(self.EQUITE)}
        self.positions = []
        alpaca_cli.list_positions = lambda: list(self.positions)
        alpaca_cli.list_open_option_positions = lambda: list(self.positions)
        alpaca_cli.get_option_ask_price = lambda s: 2.80
        alpaca_cli.find_near_the_money_contract = (
            lambda sym, direction, spot=None:
            "%s260904%s00500000" % (sym, "C" if direction > 0 else "P"))
        self.ordres = []

        def submit(contract, qty=1):
            self.ordres.append((contract, qty))
            return "ord-%d" % len(self.ordres)

        alpaca_cli.submit_paper_option_order = submit
        alpaca_cli.close_position = lambda s: {"status": "ok"}

        # Par défaut : des barres agitées jusqu'au bout, donc pas de régime
        # bon marché. Chaque test qui veut une entrée le dit explicitement.
        self.barres = {}
        alpaca_cli.get_daily_bars = lambda sym, **k: self.barres.get(
            sym, serie(self.N_BARRES, graine=7))

    def tearDown(self):
        for nom, valeur in self._sauve.items():
            setattr(alpaca_cli, nom, valeur)
        risk_gates.STATE_FILE, decision_log.LOG_FILE, risk_gates.HALT_FILE = (
            self._state, self._log, self._halt)
        config.require_credentials = self._req
        shutil.rmtree(self.tmp, ignore_errors=True)

    def lancer(self, symboles=("SPY",), dry_run=False):
        args = types.SimpleNamespace(
            symbols=",".join(symboles), dry_run=dry_run,
            sharpe_threshold=0.0, skip_market_check=False)
        record = {"dry_run": dry_run, "symbols": list(symboles),
                  "outcome": "unknown"}
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            agent._run(args, list(symboles), record)
        return record, sortie.getvalue()

    def journal(self):
        if not decision_log.LOG_FILE.exists():
            return []
        return [json.loads(l) for l in
                decision_log.LOG_FILE.read_text(encoding="utf-8").splitlines()
                if l.strip()]


class TestPipelineComplet(BaseIntegration):

    def test_une_run_complete_produit_un_verdict_par_symbole(self):
        """Le chemin nominal : trois symboles évalués pour de vrai, à travers
        la stratégie et le garde anti-fuite."""
        record, _ = self.lancer(("SPY", "GLD", "XLV"))
        verdicts = {v["symbol"]: v for v in record["verdicts"]}
        self.assertEqual(set(verdicts), {"SPY", "GLD", "XLV"})
        for v in verdicts.values():
            self.assertIsInstance(v["tradeable"], bool)
            self.assertTrue(v["reason"], "un verdict sans raison lisible")

    def test_un_regime_de_volatilite_basse_mene_a_un_ordre_reel(self):
        """De bout en bout jusqu'à la soumission : stratégie -> garde anti-fuite
        -> régime -> portes de risque -> dimensionnement -> ordre -> journal."""
        # graine=5, 60 jours calmes : combinaison CHERCHÉE, pas devinée — elle
        # produit « cheap-vol regime confirmed, hindsight_guard clean ». La
        # première version de ce test se contentait de sauter quand aucune
        # entrée ne sortait, ce qui en faisait un test qui ne prouvait rien :
        # précisément le chemin jusqu'à la soumission qu'il devait couvrir.
        self.barres = {"SPY": serie(self.N_BARRES, graine=5, calme_a_la_fin=60)}
        record, _ = self.lancer(("SPY",))
        self.assertEqual(record["outcome"], "order_submitted",
                         "le pipeline complet ne va pas jusqu'à la soumission "
                         "(verdict : %s)" % record["outcome"])
        self.assertEqual(len(self.ordres), 1)
        contrat, qty = self.ordres[0]
        self.assertTrue(contrat.startswith("SPY"))
        self.assertGreaterEqual(qty, 1)
        etat = json.loads(risk_gates.STATE_FILE.read_text(encoding="utf-8"))
        self.assertIn("SPY", etat["traded_today"]["symbols"],
                      "l'ordre est parti mais le garde anti-doublon n'est pas armé")

    def test_le_garde_anti_fuite_refuse_reellement_un_symbole(self):
        """La fonctionnalité qui donne son nom au projet, exercée de bout en
        bout et non sur la bibliothèque seule.

        graine=3 : la fenêtre HV qui gagne sur la fenêtre complète ne tient pas
        en in-sample. Le verdict le dit, aucun ordre ne part, et la raison porte
        le préfixe exact que le tableau de bord met en évidence."""
        self.barres = {"SPY": serie(self.N_BARRES, graine=3, calme_a_la_fin=60)}
        record, _ = self.lancer(("SPY",))
        verdict = record["verdicts"][0]
        self.assertFalse(verdict["tradeable"])
        self.assertTrue(verdict["reason"].startswith("hindsight_guard:"),
                        "la raison ne porte pas le préfixe que renderLeakStat() "
                        "et renderDecisions() cherchent : %r" % verdict["reason"])
        self.assertEqual(self.ordres, [],
                         "un ordre est parti sur un symbole refusé pour fuite")

    def test_un_probleme_de_donnees_n_est_pas_publie_comme_une_prise(self):
        """`report.agrees` est faux dans TROIS cas — gagnants divergents, rien
        au-dessus du seuil, ou candidate NON NOTABLE — et agent.py les résumait
        tous par la même phrase fixe en imprimant « LEAK DETECTED ».

        renderLeakStat() compte les verdicts dont la raison commence par
        « hindsight_guard: » et les annonce comme « Hindsight leaks caught » :
        le chiffre le plus mis en avant du projet. Un problème de données y
        était donc publié comme une prise du garde anti-fuite.

        Le préfixe est désormais RÉSERVÉ aux vraies prises."""
        self.barres = {"SPY": serie(325, graine=1)}      # trop peu de barres
        record, sortie = self.lancer(("SPY",))
        raison = record["verdicts"][0]["reason"]
        self.assertIn("CANNOT CONCLUDE", raison)
        self.assertFalse(
            raison.startswith("hindsight_guard:"),
            "un problème de données est compté comme une fuite attrapée par "
            "le tableau de bord : %r" % raison)
        self.assertIn("CANNOT CONCLUDE", sortie,
                      "la sortie imprime encore « LEAK DETECTED » pour un cas "
                      "où le garde dit ne pas pouvoir conclure")

    def test_les_trois_refus_du_garde_ont_trois_raisons_distinctes(self):
        """« the agent refuses to trade and prints why » (README). Une seule
        phrase pour trois pourquoi différents n'est pas une explication."""
        raisons = set()
        for barres in (serie(self.N_BARRES, graine=3, calme_a_la_fin=60),
                       serie(325, graine=1)):
            self.barres = {"SPY": barres}
            record, _ = self.lancer(("SPY",))
            raisons.add(record["verdicts"][0]["reason"])
        self.assertEqual(len(raisons), 2,
                         "deux situations différentes produisent la même "
                         "raison : %r" % raisons)

    def test_le_coupe_circuit_arrete_les_entrees_sans_toucher_aux_sorties(self):
        """L'asymétrie que le docstring de is_halted() promet, vérifiée sur le
        pipeline entier et non sur la fonction seule."""
        risk_gates.HALT_FILE.write_text("pause opérateur", encoding="utf-8")
        self.positions = [{"symbol": "SPY260904C00500000",
                           "asset_class": "us_option", "cost_basis": "500.0",
                           "unrealized_plpc": "-0.55", "qty": "1"}]
        record, _ = self.lancer(("SPY",))
        self.assertEqual(record["outcome"], "halted")
        self.assertEqual(self.ordres, [], "une entrée est passée malgré HALT")
        self.assertTrue(record["exit_actions"],
                        "les sorties ont été bloquées par HALT — elles ne "
                        "doivent jamais l'être")

    def test_un_marche_ferme_ne_declenche_rien(self):
        alpaca_cli.get_clock = lambda: {"is_open": False, "next_open": "demain"}
        record, _ = self.lancer(("SPY",))
        self.assertEqual(record["outcome"], "market_closed")
        self.assertEqual(self.ordres, [])

    def test_un_essai_a_blanc_ne_soumet_jamais_rien(self):
        """Ce test était VIDE dans sa première version, et c'est une mutation
        qui l'a montré : il utilisait une série que le garde anti-fuite refuse,
        donc aucun ordre ne partait de toute façon, et il acceptait aussi bien
        « dry_run_tradeable » que « no_edge ». Désactiver le garde --dry-run
        dans agent.py ne le faisait pas tomber.

        Il utilise désormais la série qui EST négociable, et exige le verdict
        exact : le symbole a passé toutes les portes, et seul --dry-run
        l'empêche de partir."""
        self.barres = {"SPY": serie(self.N_BARRES, graine=5, calme_a_la_fin=60)}
        record, _ = self.lancer(("SPY",), dry_run=True)
        self.assertEqual(record["outcome"], "dry_run_tradeable",
                         "prérequis : le symbole doit être négociable, sinon ce "
                         "test ne vérifie rien")
        self.assertEqual(self.ordres, [], "un --dry-run a soumis un ordre")

    def test_des_barres_tronquees_font_refuser_le_symbole(self):
        """Trop peu de barres -> certaines fenêtres HV n'ont aucun échantillon
        -> _sharpe rend NaN -> hindsight_guard refuse de certifier.

        PORTÉE EXACTE, mesurée et non supposée : ce test n'exerce PAS le
        contrôle du nombre de barres d'alpaca_cli._check_bar_quality. La
        frontière bouchée ici est get_daily_bars, qui est AU-DESSUS de lui —
        vérifié par mutation, retirer ce contrôle ne fait tomber aucun test de
        ce fichier. Ce qui est vérifié ici, c'est la SECONDE défense : même si
        des barres tronquées atteignaient la stratégie, le pipeline refuse le
        symbole et ne soumet rien. Le contrôle du nombre de barres est couvert
        séparément, par test_risk_gates.TestQualiteDesBarres."""
        self.barres = {"SPY": serie(325, graine=1)}
        record, _ = self.lancer(("SPY",))
        verdict = record["verdicts"][0]
        self.assertFalse(verdict["tradeable"])
        self.assertEqual(self.ordres, [])

    def test_un_symbole_qui_explose_n_emporte_pas_les_autres(self):
        """L'isolation par symbole, vérifiée sur le vrai chemin."""
        vrai = alpaca_cli.get_daily_bars

        def bancal(sym, **k):
            if sym == "GLD":
                raise alpaca_cli.AlpacaCLIError("panne simulée sur GLD")
            return vrai(sym, **k)

        alpaca_cli.get_daily_bars = bancal
        record, _ = self.lancer(("SPY", "GLD", "XLV"))
        verdicts = {v["symbol"]: v for v in record["verdicts"]}
        self.assertEqual(set(verdicts), {"SPY", "GLD", "XLV"},
                         "un symbole en panne a fait disparaître les autres")
        self.assertIn("panne simulée", verdicts["GLD"]["reason"])

    def test_chaque_run_laisse_une_trace_journalisee(self):
        """decision_log.jsonl est la preuve publiée. Une run qui n'y laisse
        rien est une run invisible."""
        record, _ = self.lancer(("SPY",))
        decision_log.log_run_or_dump(record)
        entrees = self.journal()
        self.assertEqual(len(entrees), 1)
        self.assertIn("timestamp", entrees[0])
        self.assertEqual(entrees[0]["outcome"], record["outcome"])


class TestMoniteurDeSorties(BaseIntegration):
    """monitor_exits.main() tourne toutes les 15 minutes sans surveillance et
    n'avait AUCUNE couverture d'intégration. C'est pourtant la seule protection
    d'une position ouverte : Alpaca ne supporte pas les ordres bracket sur
    options.

    Les pièces (manage_exits, _filter_for_logging, le statut de dernière
    exécution) sont testées séparément ; leur assemblage, jamais.
    """

    def setUp(self):
        super().setUp()
        import monitor_exits
        self.monitor = monitor_exits
        self._m = (monitor_exits.MONITOR_STATUS_FILE, monitor_exits.DEDUP_FILE)
        monitor_exits.MONITOR_STATUS_FILE = self.tmp / "monitor_last_run.json"
        monitor_exits.DEDUP_FILE = self.tmp / "dedup.json"
        self._argv = list(sys.argv)

    def tearDown(self):
        self.monitor.MONITOR_STATUS_FILE, self.monitor.DEDUP_FILE = self._m
        sys.argv = self._argv
        super().tearDown()

    def lancer_moniteur(self, dry_run=False):
        sys.argv = ["monitor_exits.py"] + (["--dry-run"] if dry_run else [])
        sortie = io.StringIO()
        with contextlib.redirect_stdout(sortie):
            self.monitor.main()
        return sortie.getvalue()

    def statut(self):
        return json.loads(
            self.monitor.MONITOR_STATUS_FILE.read_text(encoding="utf-8"))

    def _position(self, symbole, plpc):
        return {"symbol": symbole, "asset_class": "us_option",
                "cost_basis": "500.0", "unrealized_plpc": plpc, "qty": "1"}

    def test_une_position_sous_le_stop_est_fermee_et_journalisee(self):
        self.positions = [self._position("SPY260904C00500000", "-0.55")]
        fermees = []
        alpaca_cli.close_position = lambda s: fermees.append(s)
        self.lancer_moniteur()
        self.assertEqual(fermees, ["SPY260904C00500000"])
        self.assertEqual(self.statut()["outcome"], "checked")
        entrees = self.journal()
        self.assertTrue(entrees, "une vraie fermeture n'a laissé aucune trace "
                                 "dans la preuve publiée")
        self.assertEqual(entrees[-1]["run_type"], "exit_monitor")

    def test_une_position_dans_les_clous_ne_pollue_pas_le_journal(self):
        """Le moniteur tourne ~26 fois par jour de bourse. Journaliser chaque
        « je ne fais rien » noierait les vraies décisions dans la fenêtre des
        30 derniers enregistrements que le tableau de bord affiche."""
        self.positions = [self._position("SPY260904C00500000", "-0.10")]
        self.lancer_moniteur()
        self.assertEqual(self.journal(), [],
                         "un passage de routine a écrit dans decision_log.jsonl")
        self.assertEqual(self.statut()["outcome"], "checked",
                         "le statut de dernière exécution doit être écrit à "
                         "CHAQUE passage, lui — c'est ce qui distingue « page "
                         "périmée » de « moniteur mort »")

    def test_un_essai_a_blanc_ne_ferme_rien(self):
        self.positions = [self._position("SPY260904C00500000", "-0.55")]
        fermees = []
        alpaca_cli.close_position = lambda s: fermees.append(s)
        self.lancer_moniteur(dry_run=True)
        self.assertEqual(fermees, [], "un --dry-run a fermé une vraie position")

    def test_une_panne_repetee_n_est_journalisee_qu_une_fois_par_heure(self):
        """Le battement de cœur, vu depuis le processus entier : une panne
        persistante est signalée la première fois, puis étouffée jusqu'à ce que
        HEARTBEAT_SECONDS soit écoulé — sinon 26 entrées identiques par jour
        chasseraient la décision quotidienne de l'agent hors de la fenêtre."""
        self.positions = [self._position("SPY260904C00500000", "-0.55")]

        def casse(symbole):
            raise alpaca_cli.AlpacaCLIError("panne persistante")

        alpaca_cli.close_position = casse
        for _ in range(3):
            self.lancer_moniteur()
        self.assertEqual(len(self.journal()), 1,
                         "la même panne a été journalisée à chaque passage : "
                         "le battement de cœur ne fonctionne pas")

    def test_une_panne_qui_se_resout_puis_revient_est_re_signalee(self):
        """« Une signature qui cesse d'apparaître est retirée de l'état » —
        sinon un horodatage périmé la ferait taire pour toujours."""
        self.positions = [self._position("SPY260904C00500000", "-0.55")]
        alpaca_cli.close_position = lambda s: (_ for _ in ()).throw(
            alpaca_cli.AlpacaCLIError("panne A"))
        self.lancer_moniteur()
        self.assertEqual(len(self.journal()), 1)

        self.positions = []                      # la panne disparaît
        self.lancer_moniteur()
        self.assertEqual(len(self.journal()), 1, "rien de neuf à journaliser")

        self.positions = [self._position("SPY260904C00500000", "-0.55")]
        self.lancer_moniteur()
        self.assertEqual(len(self.journal()), 2,
                         "la panne est revenue et reste étouffée par un "
                         "horodatage périmé")


class TestToutDemarre(unittest.TestCase):
    """Le dépôt compte des modules qu'AUCUN test n'importe — backtest.py,
    compare_strategies.py, publish_dashboard.py, test_connection.py. Une
    faute de frappe ou un import cassé y resterait invisible jusqu'au jour où
    quelqu'un les lance.

    Ajouté le 27/08 après une journée de modifications réparties sur huit
    fichiers : « chaque pièce testée » ne dit rien de « tout démarre encore ».
    """

    RACINE = Path(__file__).resolve().parent
    MODULES = ("agent", "alpaca_cli", "config", "decision_log", "risk_gates",
               "vol_strategy", "momentum_strategy", "hindsight_guard",
               "monitor_exits", "publish_dashboard", "backtest",
               "compare_strategies")
    ENTREES = ("agent.py", "monitor_exits.py", "publish_dashboard.py",
               "backtest.py", "compare_strategies.py", "garde_fou.py")

    def _env(self):
        env = dict(os.environ)
        env.update({"ALPACA_API_KEY": "cle-de-test",
                    "ALPACA_SECRET_KEY": "secret-de-test",
                    "ALPACA_LIVE_TRADE": "false"})
        return env

    def test_chaque_module_s_importe(self):
        casses = []
        for nom in self.MODULES:
            proc = subprocess.run(
                [sys.executable, "-c", "import %s" % nom], cwd=str(self.RACINE),
                capture_output=True, text=True, timeout=60, env=self._env())
            if proc.returncode != 0:
                derniere = (proc.stderr.strip().splitlines() or [""])[-1]
                casses.append("%s (%s)" % (nom, derniere[:70]))
        self.assertEqual(casses, [], "module(s) qui ne s'importent plus : %s"
                         % "; ".join(casses))

    def test_chaque_point_d_entree_demarre(self):
        """`--help` exerce argparse ET tout le code de niveau module."""
        casses = []
        for script in self.ENTREES:
            proc = subprocess.run(
                [sys.executable, script, "--help"], cwd=str(self.RACINE),
                capture_output=True, text=True, timeout=120, env=self._env())
            if proc.returncode != 0:
                derniere = (proc.stderr.strip().splitlines() or [""])[-1]
                casses.append("%s (%s)" % (script, derniere[:70]))
        self.assertEqual(casses, [], "point(s) d'entrée qui ne démarrent plus : %s"
                         % "; ".join(casses))

    def test_aucun_module_ne_touche_au_reseau_a_l_import(self):
        """Importer un module ne doit rien déclencher. Sans cette garantie, un
        appel réseau glissé au niveau module rendrait la suite dépendante d'une
        connexion — et la CI rouge pour une raison qui n'a rien à voir."""
        code = (
            "import socket\n"
            "def _interdit(*a, **k):\n"
            "    raise AssertionError('acces reseau a l\\'import')\n"
            "socket.socket.connect = _interdit\n"
            "socket.create_connection = _interdit\n"
            "import %s\n"
        )
        casses = []
        for nom in self.MODULES:
            proc = subprocess.run(
                [sys.executable, "-c", code % nom], cwd=str(self.RACINE),
                capture_output=True, text=True, timeout=60, env=self._env())
            if proc.returncode != 0:
                casses.append(nom)
        self.assertEqual(casses, [], "module(s) touchant au réseau à l'import : "
                         "%s" % ", ".join(casses))


class TestSourcesDeVerite(unittest.TestCase):
    """backtest.py ÉCRIT BACKTEST_RESULTS.md ; garde_fou.py le RELIT pour
    valider les livrables destinés au jury. compare_strategies.py et le parseur
    des Sharpes forment le même couple.

    Rien ne vérifiait que l'écrivain et le lecteur soient d'accord. Si le format
    dérive d'un côté, le contrôle 5 se tait — et on sait qu'il se tait sans
    bloquer (« introuvable ou illisible — contrôle 5 sans effet »).
    """

    RACINE = Path(__file__).resolve().parent

    def _dans(self, nom, contenu):
        """Écrit `contenu` dans un dossier temporaire et y pointe garde_fou."""
        import garde_fou
        d = Path(tempfile.mkdtemp(prefix="hindsight-verite-"))
        (d / nom).write_text(contenu, encoding="utf-8")
        vraie = garde_fou.RACINE
        garde_fou.RACINE = str(d)
        try:
            yield garde_fou
        finally:
            garde_fou.RACINE = vraie
            shutil.rmtree(d, ignore_errors=True)

    def _parse_comparaison(self, corps):
        import garde_fou
        entete = ("| symbol | vol_strategy: window | agrees? | in-sample Sharpe |\n"
                  "|---|---|---|---|\n")
        d = Path(tempfile.mkdtemp(prefix="hindsight-verite-"))
        (d / "STRATEGY_COMPARISON.md").write_text(entete + corps, encoding="utf-8")
        vraie = garde_fou.RACINE
        garde_fou.RACINE = str(d)
        try:
            return garde_fou._parse_strategy_comparison()
        finally:
            garde_fou.RACINE = vraie
            shutil.rmtree(d, ignore_errors=True)

    def test_ce_que_backtest_ecrit_est_relu_a_l_identique(self):
        """L'aller-retour complet, avec les VRAIES fonctions des deux côtés."""
        import backtest
        import garde_fou

        def barres(graine, calme):
            prix, out, x = 100.0, [], graine
            n = vol_strategy.MIN_TRADING_DAYS_FOR_SWEEP + 20
            for i in range(n):
                x = (1103515245 * x + 12345) % (2 ** 31)
                amp = 1000 if i < n - calme else 25
                prix *= 1.0 + ((x % (2 * amp + 1)) - amp) / 100000.0
                out.append(vol_strategy.Bar(close=prix))
            return out

        # graine 3 produit une FUITE, graine 5 un symbole propre : les deux
        # branches du parseur sont exercées.
        res = [backtest.backtest_symbol("SPY", barres(5, 60)),
               backtest.backtest_symbol("XLK", barres(3, 60))]
        d = Path(tempfile.mkdtemp(prefix="hindsight-verite-"))
        (d / "BACKTEST_RESULTS.md").write_text(
            backtest.format_report(res), encoding="utf-8")
        vraie = garde_fou.RACINE
        garde_fou.RACINE = str(d)
        try:
            relu = garde_fou._parse_backtest_results()
        finally:
            garde_fou.RACINE = vraie
            shutil.rmtree(d, ignore_errors=True)

        self.assertIsNotNone(relu, "garde_fou ne sait plus lire ce que "
                                   "backtest.py vient d'écrire")
        for r in res:
            sym = r["symbol"]
            verdict = r["hindsight_guard_verdict"]
            w = r["windows"][verdict["full_winner"]]
            self.assertIn(sym, relu)
            self.assertEqual(relu[sym]["leaked"], not verdict["agrees"])
            self.assertEqual(relu[sym]["win_rate"], w["win_rate_on_trade_days_pct"])
            self.assertEqual(relu[sym]["concentration"], w["top5_share_pct"])
            self.assertEqual(relu[sym]["trade_days"], w["trade_days"])

    def test_un_sharpe_negatif_ne_fait_pas_disparaitre_le_symbole(self):
        r"""Le motif était `([\d.]+)`, incapable de matcher un signe moins. Un
        Sharpe in-sample négatif n'est pas une anomalie ici : c'est l'histoire
        d'origine du projet."""
        r = self._parse_comparaison(
            "| SPY | 10d | yes | -0.750 |\n| GLD | 20d | yes | 1.956 |\n")
        self.assertEqual(sorted(r or {}), ["GLD", "SPY"],
                         "un symbole au Sharpe négatif disparaît de l'ensemble "
                         "de référence, en silence")
        self.assertEqual(r["SPY"]["sharpe"], -0.75)

    def test_un_sharpe_nan_ne_fait_pas_disparaitre_le_symbole(self):
        """Depuis le correctif de _sharpe du 27/08, nan est une valeur légitime
        du rapport."""
        r = self._parse_comparaison(
            "| SPY | 10d | yes | nan |\n| GLD | 20d | yes | 1.956 |\n")
        self.assertEqual(sorted(r or {}), ["GLD", "SPY"])
        self.assertFalse(math.isfinite(r["SPY"]["sharpe"]))

    def test_tous_negatifs_ne_vide_pas_le_controle(self):
        """Le pire cas : le parseur rendait None, donc l'ensemble de référence
        était vide et le contrôle du Sharpe était sauté ENTIÈREMENT."""
        r = self._parse_comparaison(
            "| SPY | 10d | yes | -0.750 |\n| GLD | 20d | yes | -1.200 |\n")
        self.assertEqual(sorted(r or {}), ["GLD", "SPY"])

    def test_un_format_illisible_est_signale_et_non_confondu_avec_une_absence(self):
        import garde_fou
        # La liste s'appelle `alertes`, en minuscules. La première version de ce
        # test testait `hasattr(garde_fou, "ALERTES")` — faux — et sautait donc
        # son assertion en silence. Un test qui ne vérifie rien passe toujours ;
        # on nomme l'attribut sans repli, pour que le renommer fasse tomber le
        # test au lieu de le vider.
        avant = len(garde_fou.alertes)
        r = self._parse_comparaison("SPY vol_strategy 10 jours yes 1.598\n")
        self.assertIsNone(r, "prérequis : rien ne doit être lisible ici")
        self.assertGreater(len(garde_fou.alertes), avant,
                           "un fichier présent mais illisible est traité comme "
                           "un fichier absent, sans un mot")
        self.assertIn("format a change", garde_fou.alertes[-1][1])


class TestLecteursDeCodeSource(unittest.TestCase):
    """garde_fou.py lit DEFAULT_UNIVERSE et les huit seuils de risque
    DIRECTEMENT dans le code — c'est ce qui rend le croisement des livrables
    mécanique plutôt que déclaratif.

    Deux façons pour ces lecteurs de se tromper, toutes deux mesurées le 27/08 :
    ne rien lire sans le dire, et lire la MAUVAISE valeur.
    """

    RACINE = Path(__file__).resolve().parent

    def _dossier(self, fichier=None, ancien=None, nouveau=None):
        d = Path(tempfile.mkdtemp(prefix="hindsight-lecteurs-"))
        for nom in ("agent.py", "risk_gates.py", "vol_strategy.py",
                    "monitor_exits.py"):
            shutil.copy(self.RACINE / nom, d / nom)
        if fichier:
            chemin = d / fichier
            avant = chemin.read_text(encoding="utf-8")
            apres = re.sub(ancien, nouveau, avant, count=1, flags=re.M)
            self.assertNotEqual(avant, apres,
                                "la mutation %r n'a rien changé : le fichier a "
                                "changé de forme et ce test ne vérifie plus "
                                "rien" % ancien)
            chemin.write_text(apres, encoding="utf-8")
        return d

    def _avec(self, dossier, fn):
        import garde_fou
        vraie = garde_fou.RACINE
        avant = len(garde_fou.alertes)
        garde_fou.RACINE = str(dossier)
        try:
            resultat = fn(garde_fou)
        finally:
            garde_fou.RACINE = vraie
            shutil.rmtree(dossier, ignore_errors=True)
            nouvelles = garde_fou.alertes[avant:]
        return resultat, [a[1] for a in nouvelles]

    def test_les_huit_seuils_sont_lisibles_dans_le_depot_reel(self):
        """Contrôle : sans lui, un lecteur qui échoue TOUJOURS passerait les
        tests ci-dessous."""
        import garde_fou
        valeurs, alertes = self._avec(
            self._dossier(), lambda gf: gf._parse_seuils_risque())
        self.assertEqual(len(valeurs), len(garde_fou.SEUILS_RISQUE),
                         "seuil(s) non lu(s) : %s"
                         % sorted({n for n, _ in garde_fou.SEUILS_RISQUE}
                                  - set(valeurs)))
        self.assertEqual(alertes, [])

    def test_un_seuil_refactore_est_nomme_et_non_saute(self):
        """`MAX_TOTAL_RISK_PCT = 3 / 100` est un refactor parfaitement
        légitime."""
        valeurs, alertes = self._avec(
            self._dossier("risk_gates.py",
                          r"^MAX_TOTAL_RISK_PCT = 0\.03.*$",
                          "MAX_TOTAL_RISK_PCT = 3 / 100"),
            lambda gf: gf._parse_seuils_risque())
        self.assertNotIn("MAX_TOTAL_RISK_PCT", valeurs)
        self.assertTrue(any("MAX_TOTAL_RISK_PCT" in a for a in alertes),
                        "un seuil qui échappe au contrôle n'est pas nommé : "
                        "le livrable pourrait annoncer n'importe quoi pour lui")

    def test_un_seuil_calcule_n_est_jamais_lu_de_travers(self):
        """LE point important : ce n'était pas un saut silencieux mais une
        MAUVAISE LECTURE. `3 / 100` donnait 3.0 au lieu de 0.03, et le contrôle
        validait ensuite les livrables contre une référence fausse — le chiffre
        VRAI aurait été signalé comme erroné."""
        valeurs, _ = self._avec(
            self._dossier("risk_gates.py",
                          r"^MAX_SECTOR_EXPOSURE_PCT = 0\.015.*$",
                          "MAX_SECTOR_EXPOSURE_PCT = 1.5 / 100"),
            lambda gf: gf._parse_seuils_risque())
        self.assertNotIn("MAX_SECTOR_EXPOSURE_PCT", valeurs,
                         "le lecteur a rendu %r pour une valeur qui vaut 0.015"
                         % valeurs.get("MAX_SECTOR_EXPOSURE_PCT"))

    def test_un_univers_illisible_est_signale(self):
        univers, alertes = self._avec(
            self._dossier("agent.py",
                          r"^DEFAULT_UNIVERSE = \[[^\]]*\]",
                          'DEFAULT_UNIVERSE = list(map(str.upper, ("spy",)))'),
            lambda gf: gf._parse_univers_actuel())
        self.assertIsNone(univers)
        self.assertTrue(any("DEFAULT_UNIVERSE" in a for a in alertes),
                        "le croisement de l'univers disparaît sans un mot")

    def test_un_univers_normal_ne_declenche_rien(self):
        univers, alertes = self._avec(
            self._dossier(), lambda gf: gf._parse_univers_actuel())
        self.assertTrue(univers)
        self.assertEqual(alertes, [])


class TestLivrablesCroisesAvecLaSource(unittest.TestCase):
    """Le contrôle 5 vérifie ligne par ligne que le tableau symbole-par-symbole
    des livrables dit ce que BACKTEST_RESULTS.md dit.

    Mesuré le 27/08 en mutant le README : sur les quatre champs de ce tableau,
    DEUX seulement étaient croisés.

        taux de réussite faussé   -> 🔴 REFUSÉ
        concentration faussée     -> 🔴 REFUSÉ
        nombre de transactions    -> code 0, laissé passer
        statut de fuite inversé   -> code 0, laissé passer

    Le dernier est le plus grave : le README pouvait annoncer XLK PROPRE alors
    que la source mécanique le donne EN FUITE. C'est la revendication centrale
    du projet — « this check finds a genuine disagreement on XLK and refuses it
    live, every run » — et le contrôle qui existe pour l'empêcher ne regardait
    pas cette colonne.
    """

    RACINE = Path(__file__).resolve().parent
    FICHIERS = ("garde_fou.py", "README.md", "BACKTEST_RESULTS.md",
                "STRATEGY_COMPARISON.md", "agent.py", "risk_gates.py",
                "vol_strategy.py", "monitor_exits.py")

    def _verdict(self, ancien=None, nouveau=None):
        d = Path(tempfile.mkdtemp(prefix="hindsight-livrables-"))
        try:
            for nom in self.FICHIERS:
                source = self.RACINE / nom
                if not source.exists():
                    self.skipTest("%s absent" % nom)
                shutil.copy(source, d / nom)
            if ancien is not None:
                chemin = d / "README.md"
                avant = chemin.read_text(encoding="utf-8")
                self.assertEqual(avant.count(ancien), 1,
                                 "la ligne mutée n'apparaît pas exactement une "
                                 "fois : le README a changé de forme et ce test "
                                 "ne vérifie plus rien")
                chemin.write_text(avant.replace(ancien, nouveau), encoding="utf-8")
            proc = subprocess.run([sys.executable, "garde_fou.py"], cwd=str(d),
                                  capture_output=True, text=True, timeout=120)
            return proc.returncode, proc.stdout + proc.stderr
        finally:
            shutil.rmtree(d, ignore_errors=True)

    SPY = "| SPY | 10d | ✅ clean | 102 | 45.1% | 82.6% |"
    XLV = "| XLV | 10d | ✅ clean | 52 | 50.0% | 78.2% |"
    XLK = ("| XLK | 90d | 🛡️ **LEAK — refused live** | 76 (not traded) "
           "| 36.8% | 136.7% |")

    # Les messages que ce contrôle produit. On assert sur EUX, pas sur le code
    # de sortie : le dossier de test ne contient que les fichiers nécessaires au
    # contrôle 5, donc d'autres contrôles y bloquent pour des fichiers absents,
    # sans rapport. Trouvé en écrivant ce test — le contrôle « dépôt sain »
    # échouait sur un code 1 qui ne disait rien de ce qu'il vérifie.
    MESSAGES = ("annonce PROPRE", "annonce EN FUITE", "NOMBRE DE TRANSACTIONS",
                "WIN RATE", "CONCENTRATION")

    def test_le_depot_sain_ne_declenche_aucun_de_ces_messages(self):
        """Contrôle : sans lui, un contrôle qui crie TOUJOURS passerait les
        quatre tests ci-dessous."""
        _, sortie = self._verdict()
        declenches = [m for m in self.MESSAGES if m in sortie]
        self.assertEqual(declenches, [],
                         "le tableau du README correspond à la source mécanique "
                         "et le contrôle proteste quand même : %s" % declenches)

    def test_une_fuite_cachee_est_refusee(self):
        """Le README annonce XLK propre ; la source mécanique dit qu'il fuit."""
        code, sortie = self._verdict(
            self.XLK, "| XLK | 90d | ✅ clean | 76 | 36.8% | 136.7% |")
        self.assertIn("annonce PROPRE", sortie,
                      "un livrable peut annoncer le contraire de la source "
                      "mécanique sur la revendication centrale du projet")
        self.assertNotEqual(code, 0, "le message est là mais le verdict passe")

    def test_une_fuite_inventee_est_refusee_aussi(self):
        """L'autre sens compte autant : annoncer une prise qui n'a pas eu lieu
        gonflerait le résultat du projet."""
        code, sortie = self._verdict(
            self.SPY, "| SPY | 10d | 🛡️ **LEAK — refused live** | 102 | 45.1% | 82.6% |")
        self.assertIn("annonce EN FUITE", sortie)
        self.assertNotEqual(code, 0)

    def test_un_nombre_de_transactions_fausse_est_refuse(self):
        code, sortie = self._verdict(
            self.XLV, "| XLV | 10d | ✅ clean | 152 | 50.0% | 78.2% |")
        self.assertIn("NOMBRE DE TRANSACTIONS", sortie)
        self.assertNotEqual(code, 0)

    def test_le_nombre_de_fuites_annonce_par_le_deck_est_croise(self):
        """« 1 leak caught » est le chiffre phare du deck — celui qu'un juge
        retient. Le contrôle existait et fonctionnait, mais n'avait aucun test.

        Ce test mute la SOURCE plutôt que le livrable : on retire les marqueurs
        de fuite de BACKTEST_RESULTS.md, et le deck qui annonce toujours « 1 »
        doit être refusé. C'est aussi le seul croisement qui atteint le deck :
        son texte extrait d'un .pptx n'a pas de tableau Markdown, donc le
        contrôle par symbole ne s'y applique pas — par construction, pas par
        oubli."""
        d = Path(tempfile.mkdtemp(prefix="hindsight-leaks-"))
        try:
            for nom in self.FICHIERS:
                source = self.RACINE / nom
                if not source.exists():
                    self.skipTest("%s absent" % nom)
                shutil.copy(source, d / nom)
            deck = self.RACINE / "submission" / "Hindsight_Alpha_Deck.pptx"
            if not deck.exists():
                self.skipTest("deck absent")
            (d / "submission").mkdir(exist_ok=True)
            shutil.copy(deck, d / "submission" / "Hindsight_Alpha_Deck.pptx")

            chemin = d / "BACKTEST_RESULTS.md"
            avant = chemin.read_text(encoding="utf-8")
            apres = re.sub(r"LEAK DETECTED[^\n]*", "OK: no leak",
                           avant.replace("**LEAK**", "yes"))
            self.assertNotEqual(avant, apres,
                                "aucun marqueur de fuite dans la source : ce "
                                "test ne vérifie plus rien")
            chemin.write_text(apres, encoding="utf-8")

            proc = subprocess.run([sys.executable, "garde_fou.py"], cwd=str(d),
                                  capture_output=True, text=True, timeout=120)
            sortie = proc.stdout + proc.stderr
        finally:
            shutil.rmtree(d, ignore_errors=True)
        self.assertIn("NOMBRE DE LEAKS", sortie,
                      "le deck annonce un nombre de fuites que la source ne "
                      "confirme pas, et rien ne le dit")
        self.assertIn("Deck", sortie)

    def test_les_deux_champs_deja_couverts_le_restent(self):
        """Anti-régression : élargir un contrôle ne doit pas en casser une
        partie qui marchait."""
        code, sortie = self._verdict(
            self.SPY, "| SPY | 10d | ✅ clean | 102 | 55.1% | 82.6% |")
        self.assertIn("WIN RATE", sortie)
        self.assertNotEqual(code, 0)


class TestVerrouDitHebdomadaire(unittest.TestCase):
    """risk_gates.py titre son propre commentaire « NOM TROMPEUR » et écrit :
    « Ce verrou n'est pas hebdomadaire. » Il compare l'équité courante à une
    référence posée UNE FOIS, sans aucune remise à zéro en fin de semaine.

    Le README porte la correction. Les trois autres livrables — ceux qu'un jury
    lit — décrivaient un verrou qui repart à zéro chaque semaine. Il ne repart
    jamais : un lecteur en déduirait que l'agent reprend le lundi suivant.

    Ces tests portent sur le COMPORTEMENT du contrôle, pas sur l'état actuel des
    livrables : asserter « ces trois fichiers sont signalés » deviendrait faux
    le jour où ils sont reformulés, et un test qui casse quand on corrige le
    dossier est un test qui décourage de le corriger.
    """

    def _alertes(self, contenu):
        import garde_fou
        d = Path(tempfile.mkdtemp(prefix="hindsight-hebdo-"))
        (d / "README.md").write_text(contenu, encoding="utf-8")
        vraie = garde_fou.RACINE
        avant = len(garde_fou.alertes)
        garde_fou.RACINE = str(d)
        try:
            garde_fou.controle_verrou_dit_hebdomadaire()
            return [a[1] for a in garde_fou.alertes[avant:]]
        finally:
            garde_fou.RACINE = vraie
            del garde_fou.alertes[avant:]
            shutil.rmtree(d, ignore_errors=True)

    def test_une_formulation_hebdomadaire_seule_est_signalee(self):
        alertes = self._alertes("The agent has a 3% weekly drawdown lock.")
        self.assertTrue(alertes, "un livrable décrit le verrou comme "
                                 "hebdomadaire et rien ne le dit")
        self.assertIn("HEBDOMADAIRE", alertes[0])

    def test_le_francais_aussi(self):
        alertes = self._alertes(
            "Un verrou automatique si le compte perd 3% sur la semaine.")
        self.assertTrue(alertes)

    def test_la_nuance_presente_desamorce_l_alerte(self):
        """C'est ainsi que le README reste vert : il dit « weekly » ET
        explique que ce n'est pas hebdomadaire."""
        alertes = self._alertes(
            "Named \"weekly\" in the code, but measured from the first "
            "recorded equity — there is no week-boundary reset.")
        self.assertEqual(alertes, [])

    def test_un_texte_sans_rapport_ne_declenche_rien(self):
        """Contrôle : « week » seul ne suffit pas, sinon toute mention de la
        semaine du hackathon déclencherait."""
        alertes = self._alertes(
            "The dashboard is republished every day of the judged week.")
        self.assertEqual(alertes, [])

    def test_le_README_reel_reste_vert(self):
        """Le README porte la nuance aujourd'hui. S'il la perdait, ce test
        tomberait — c'est le but."""
        import garde_fou
        avant = len(garde_fou.alertes)
        try:
            garde_fou.controle_verrou_dit_hebdomadaire()
            nouvelles = [a for a in garde_fou.alertes[avant:]
                         if a[0].endswith("README.md")]
        finally:
            del garde_fou.alertes[avant:]
        self.assertEqual(nouvelles, [],
                         "le README a perdu la nuance « no week-boundary reset »")


class TestFenetresCitees(unittest.TestCase):
    """Deux livrables citent NOMMÉMENT les deux fenêtres du verdict de fuite :

        Writeup : « XLK currently fails hindsight_guard (full-window winner
                    90d, in-sample winner 10d disagree) »
        Deck    : « XLK's full-history winner (90d) disagrees with its
                    in-sample winner (10d) »

    Vérifié à la main : les deux disent VRAI aujourd'hui. Mais ces nombres
    n'étaient reliés à rien — régénérer le backtest et voir XLK basculer sur
    d'autres fenêtres rendrait les deux faux, en silence, sur la phrase même
    qui illustre la revendication centrale du projet.
    """

    RACINE = Path(__file__).resolve().parent

    def _sortie(self, mutation=None):
        d = Path(tempfile.mkdtemp(prefix="hindsight-fenetres-"))
        try:
            for nom in ("garde_fou.py", "README.md", "BACKTEST_RESULTS.md",
                        "STRATEGY_COMPARISON.md", "agent.py", "risk_gates.py",
                        "vol_strategy.py", "monitor_exits.py"):
                src = self.RACINE / nom
                if not src.exists():
                    self.skipTest("%s absent" % nom)
                shutil.copy(src, d / nom)
            for sous in ("Video_Script.md", "Hindsight_Alpha_Writeup.docx",
                         "Hindsight_Alpha_Deck.pptx"):
                src = self.RACINE / "submission" / sous
                if src.exists():
                    (d / "submission").mkdir(exist_ok=True)
                    shutil.copy(src, d / "submission" / sous)
            if mutation:
                chemin = d / "BACKTEST_RESULTS.md"
                avant = chemin.read_text(encoding="utf-8")
                ancien, nouveau = mutation
                self.assertEqual(avant.count(ancien), 1,
                                 "la ligne de verdict a changé de forme : ce "
                                 "test ne vérifie plus rien")
                chemin.write_text(avant.replace(ancien, nouveau), encoding="utf-8")
            proc = subprocess.run([sys.executable, "garde_fou.py"], cwd=str(d),
                                  capture_output=True, text=True, timeout=120)
            return proc.stdout + proc.stderr
        finally:
            shutil.rmtree(d, ignore_errors=True)

    VERDICT_XLK = ("LEAK DETECTED — full-window winner: 90 days, "
                   "in-sample winner: 10 days.")

    def test_le_depot_sain_ne_declenche_rien(self):
        """LE contrôle qui compte ici : la première version de ce croisement
        cherchait les fenêtres dans les 200 caractères SUIVANT chaque symbole,
        et attribuait le « 90d » de XLK à XLV — parce que le writeup liste
        « SPY, GLD, XLK, XLV » deux phrases plus haut. C'est le piège de
        proximité que ce fichier décrit ailleurs, et j'y suis tombé."""
        self.assertNotIn("FENETRE", self._sortie(),
                         "faux positif : une fenêtre est attribuée au mauvais "
                         "symbole")

    def test_une_fenetre_pleine_qui_derive_est_attrapee(self):
        sortie = self._sortie((self.VERDICT_XLK,
                               "LEAK DETECTED — full-window winner: 60 days, "
                               "in-sample winner: 10 days."))
        self.assertIn("FENETRE PLEINE", sortie)
        self.assertIn("XLK", sortie)

    def test_une_fenetre_in_sample_qui_derive_est_attrapee(self):
        sortie = self._sortie((self.VERDICT_XLK,
                               "LEAK DETECTED — full-window winner: 90 days, "
                               "in-sample winner: 30 days."))
        self.assertIn("FENETRE IN-SAMPLE", sortie)

    def test_les_deux_livrables_concernes_sont_nommes(self):
        """Le write-up ET le deck citent ces nombres. En signaler un seul
        laisserait l'autre faux."""
        sortie = self._sortie((self.VERDICT_XLK,
                               "LEAK DETECTED — full-window winner: 60 days, "
                               "in-sample winner: 30 days."))
        for attendu in ("Writeup", "Deck"):
            if (self.RACINE / "submission").glob("*%s*" % attendu):
                self.assertIn(attendu, sortie,
                              "%s cite ces fenêtres et n'est pas signalé" % attendu)


class TestReadmeEtPlistsSAccordent(unittest.TestCase):
    """Le README documente EN GRAS : « This is a deliberate change to a rule
    this project used to hold » — la publication du tableau de bord est
    automatique, la règle précédente est amendée là plutôt qu'ignorée.

    Le 27/08, j'ai retiré `--git-push` du plist en m'appuyant sur la docstring
    de publish_dashboard.py — que ce paragraphe déclare justement périmée. Une
    décision réfléchie et documentée annulée en croyant corriger un oubli,
    parce que RIEN ne reliait le README aux plists.

    Ces tests portent sur le COMPORTEMENT du contrôle : ils restent valides
    quelle que soit la façon dont le désaccord est tranché.
    """

    PLIST = ('<?xml version="1.0"?>\n<plist version="1.0"><dict>\n'
             '  <key>ProgramArguments</key>\n  <array>\n'
             '    <string>/usr/bin/python3</string>\n'
             '    <string>/x/publish_dashboard.py</string>\n'
             '%s'
             '  </array>\n</dict></plist>\n')

    def _alertes(self, readme, options=()):
        import garde_fou
        d = Path(tempfile.mkdtemp(prefix="hindsight-plists-"))
        (d / "launchagents").mkdir()
        lignes = "".join("    <string>%s</string>\n" % o for o in options)
        (d / "launchagents" / "com.hindsightalpha.publish-dashboard.plist"
         ).write_text(self.PLIST % lignes, encoding="utf-8")
        (d / "README.md").write_text(readme, encoding="utf-8")
        vraie = garde_fou.RACINE
        avant = len(garde_fou.alertes)
        garde_fou.RACINE = str(d)
        try:
            garde_fou.controle_readme_decrit_les_agents()
            return [a[1] for a in garde_fou.alertes[avant:]]
        finally:
            garde_fou.RACINE = vraie
            del garde_fou.alertes[avant:]
            shutil.rmtree(d, ignore_errors=True)

    NOMME = ("`launchagents/com.hindsightalpha.publish-dashboard.plist` runs\n"
             "`publish_dashboard.py %s` every 30 minutes.\n")

    def test_le_readme_promet_une_option_que_le_plist_n_a_pas(self):
        """L'erreur exacte du 27/08."""
        alertes = self._alertes(self.NOMME % "--git-push", options=())
        self.assertTrue(alertes, "le README décrit un comportement que le "
                                 "plist ne produit plus, et rien ne le dit")
        self.assertIn("--git-push", alertes[0])

    def test_le_plist_fait_une_chose_que_le_readme_ne_dit_pas(self):
        """L'autre sens compte autant : un comportement automatique non
        documenté est un comportement que personne n'a décidé."""
        alertes = self._alertes(self.NOMME % "", options=("--git-push",))
        self.assertTrue(alertes)
        self.assertIn("--git-push", alertes[0])

    def test_une_option_documentee_AILLEURS_dans_le_readme_compte(self):
        """Ce contrôle ne regardait que la PREMIÈRE mention du plist.

        Trouvé le 27/08, aussitôt après avoir complété l'inventaire du README :
        en y ajoutant le plist de publication, sa première mention est devenue
        cette liste — qui ne cite aucune option — alors que la description
        complète, avec --git-push, est 70 lignes plus bas. Le contrôle a signalé
        un désaccord inexistant, créé par ma propre édition.

        Un README a le droit de nommer un agent à plusieurs endroits : c'est
        même le signe qu'il est bien documenté."""
        readme = ("Inventaire : `com.hindsightalpha.publish-dashboard.plist`, "
                  "l'agent de publication.\n"
                  + "blabla sans rapport\n" * 40
                  + "`com.hindsightalpha.publish-dashboard.plist` runs "
                    "`publish_dashboard.py --git-push` every 30 minutes.\n")
        self.assertEqual(self._alertes(readme, options=("--git-push",)), [],
                         "une option documentée ailleurs dans le README est "
                         "signalée comme absente")

    def test_quand_les_deux_s_accordent_rien_ne_se_declenche(self):
        """Contrôle : sans lui, alerter TOUJOURS passerait les deux tests
        ci-dessus."""
        self.assertEqual(
            self._alertes(self.NOMME % "--git-push", options=("--git-push",)),
            [])

    def test_une_option_seulement_en_commentaire_ne_compte_pas_comme_active(self):
        """Le plist porte la RAISON du retrait en commentaire XML. Compter cette
        mention comme une option active masquerait précisément le désaccord."""
        import garde_fou
        d = Path(tempfile.mkdtemp(prefix="hindsight-plists-"))
        try:
            (d / "launchagents").mkdir()
            (d / "launchagents" / "com.hindsightalpha.publish-dashboard.plist"
             ).write_text(self.PLIST % "    <!-- retire : <string>--git-push</string> -->\n",
                          encoding="utf-8")
            (d / "README.md").write_text(self.NOMME % "--git-push", encoding="utf-8")
            vraie, avant = garde_fou.RACINE, len(garde_fou.alertes)
            garde_fou.RACINE = str(d)
            try:
                garde_fou.controle_readme_decrit_les_agents()
                alertes = [a[1] for a in garde_fou.alertes[avant:]]
            finally:
                garde_fou.RACINE = vraie
                del garde_fou.alertes[avant:]
        finally:
            shutil.rmtree(d, ignore_errors=True)
        self.assertTrue(alertes, "une option seulement citée en commentaire est "
                                 "comptée comme active : le désaccord disparaît")

    def test_un_agent_que_le_readme_ne_nomme_pas_est_signale(self):
        """CE TEST DISAIT L'INVERSE : il admettait qu'un plist non nommé soit
        ignoré en silence.

        Trouvé le 27/08 en lisant l'inventaire du README, qui annonçait « the
        two macOS scheduling definitions » alors qu'il y en a TROIS — et en
        mesurant : le plist du moniteur n'était nommé NULLE PART dans le
        README, contrairement aux deux autres.

        Un agent planifié que la documentation ne nomme pas est un comportement
        automatique que personne n'a décidé. Même règle que dans l'autre sens."""
        alertes = self._alertes("Ce README ne parle d'aucun agent.\n",
                                options=("--git-push",))
        self.assertTrue(alertes, "un plist non documenté passe en silence")
        self.assertIn("ne nomme nulle part", alertes[0])

    def test_le_README_reel_nomme_les_trois_agents(self):
        """Sur le vrai dépôt : les trois plists doivent être nommés. Le
        moniteur ne l'était pas — le README le désignait par le nom de son
        SCRIPT, jamais par celui de son plist."""
        import garde_fou
        avant = len(garde_fou.alertes)
        try:
            garde_fou.controle_readme_decrit_les_agents()
            manquants = [a for a in garde_fou.alertes[avant:]
                         if "ne nomme nulle part" in a[1]]
        finally:
            del garde_fou.alertes[avant:]
        self.assertEqual(manquants, [],
                         "un agent planifié n'est nommé nulle part dans le README")


GIT = shutil.which("git")


class TestAucunIdentifiantPublie(unittest.TestCase):
    """decision_log.jsonl et docs/data.json ne sont PAS gitignorés : ce sont les
    preuves publiées, et depuis le rétablissement de la publication automatique
    elles partent sur le dépôt PUBLIC toutes les 30 minutes sans intervention.

    Le chemin par lequel une clé pourrait y entrer : alpaca_cli.run(), quand la
    sortie du CLI n'est pas du JSON, lève avec « first 500 chars of output:
    {stdout[:500]} » — la sortie BRUTE. Les identifiants sont dans
    l'environnement de ce sous-processus. Un CLI en « Alpha Preview » qui
    recracherait son environnement ou une URL signée suffirait.

    Deux couches : caviardage à l'ÉCRITURE (decision_log), et contrôle de ce qui
    est DÉJÀ sur le disque (garde_fou), y compris des lignes écrites avant que
    le caviardage existe.

    Une clé poussée sur un dépôt public est publique pour toujours : c'est le
    seul défaut irréversible que ce projet puisse produire.
    """

    CLE = "CLEFACTICEPOURLETEST1234567890"
    SECRET = "SECRETFACTICEPOURLETEST0987654321"

    # ── couche 1 : caviardage a l'ecriture ────────────────────────────────
    def _journalise(self, record, cle=None, secret=None):
        import decision_log
        d = Path(tempfile.mkdtemp(prefix="hindsight-caviard-"))
        vrai, avant = decision_log.LOG_FILE, dict(os.environ)
        decision_log.LOG_FILE = d / "decision_log.jsonl"
        os.environ["ALPACA_API_KEY"] = cle if cle is not None else self.CLE
        os.environ["ALPACA_SECRET_KEY"] = secret if secret is not None else self.SECRET
        try:
            decision_log.log_run(record)
            return decision_log.LOG_FILE.read_text(encoding="utf-8").strip()
        finally:
            decision_log.LOG_FILE = vrai
            os.environ.clear()
            os.environ.update(avant)
            shutil.rmtree(d, ignore_errors=True)

    def test_une_cle_est_caviardee_a_n_importe_quelle_profondeur(self):
        ligne = self._journalise({
            "outcome": "error",
            "error": "output: ALPACA_API_KEY=%s" % self.CLE,
            "trades": [{"symbol": "SPY",
                        "error": "url=https://x/?key=%s" % self.CLE}],
        })
        self.assertNotIn(self.CLE, ligne,
                         "une clé API atteint un fichier committé et poussé "
                         "automatiquement sur un dépôt public")
        self.assertIn("CAVIARDE", ligne)
        rec = json.loads(ligne)
        self.assertEqual(rec["outcome"], "error",
                         "le caviardage a cassé le JSON")
        self.assertIn("SPY", rec["trades"][0]["symbol"],
                      "le caviardage a mangé autre chose que la clé")

    def test_le_secret_aussi(self):
        ligne = self._journalise({"outcome": "error",
                                  "error": "secret=%s" % self.SECRET})
        self.assertNotIn(self.SECRET, ligne)

    def test_une_valeur_trop_courte_ne_fait_pas_tout_disparaitre(self):
        """Contrôle : une variable vide ou d'un caractère caviarderait le
        journal entier si le seuil de longueur n'existait pas."""
        ligne = self._journalise(
            {"outcome": "no_edge", "reason": "volatility not cheap today"},
            cle="a", secret="")
        self.assertIn("volatility not cheap today", ligne)
        self.assertNotIn("CAVIARDE", ligne)

    # ── couche 2 : le controle sur ce qui est deja sur le disque ──────────
    def _verdict(self, contenu_journal=None, contenu_data=None):
        import garde_fou
        d = Path(tempfile.mkdtemp(prefix="hindsight-fuite-"))
        try:
            shutil.copy(Path(garde_fou.__file__).resolve().parent / "garde_fou.py",
                        d / "garde_fou.py")
            (d / ("." + "env")).write_text(
                "ALPACA_API_KEY=%s\nALPACA_SECRET_KEY=%s\n"
                % (self.CLE, self.SECRET), encoding="utf-8")
            if contenu_journal is not None:
                (d / "decision_log.jsonl").write_text(contenu_journal,
                                                      encoding="utf-8")
            if contenu_data is not None:
                (d / "docs").mkdir(exist_ok=True)
                (d / "docs" / "data.json").write_text(contenu_data,
                                                      encoding="utf-8")
            proc = subprocess.run([sys.executable, "garde_fou.py"], cwd=str(d),
                                  capture_output=True, text=True, timeout=120)
            return proc.stdout + proc.stderr
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_une_cle_dans_le_journal_committe_bloque(self):
        sortie = self._verdict(
            contenu_journal='{"outcome":"error","error":"key=%s"}\n' % self.CLE)
        self.assertIn("CONTIENT LA VALEUR DE ALPACA_API_KEY", sortie)
        self.assertIn("REVOQUER", sortie,
                      "le message ne dit pas quoi faire : une clé déjà poussée "
                      "doit être révoquée, pas seulement retirée du fichier")

    def test_une_cle_dans_data_json_bloque_aussi(self):
        sortie = self._verdict(contenu_data='{"x":"%s"}' % self.SECRET)
        self.assertIn("CONTIENT LA VALEUR DE ALPACA_SECRET_KEY", sortie)

    def _depot_git(self, fichiers):
        """Un vrai depot git, parce que le controle balaie `git ls-files`."""
        import garde_fou
        d = Path(tempfile.mkdtemp(prefix="hindsight-suivis-"))
        shutil.copy(Path(garde_fou.__file__).resolve().parent / "garde_fou.py",
                    d / "garde_fou.py")
        (d / ("." + "env")).write_text(
            "ALPACA_API_KEY=%s\nALPACA_SECRET_KEY=%s\nALPACA_ACCOUNT_ID=%s\n"
            % (self.CLE, self.SECRET, self.COMPTE), encoding="utf-8")
        for nom, contenu in fichiers.items():
            (d / nom).write_text(contenu, encoding="utf-8")
        for args in (["init", "-q", "."], ["add", "-A"]):
            subprocess.run([GIT] + args, cwd=str(d), capture_output=True,
                           timeout=30)
        proc = subprocess.run([sys.executable, "garde_fou.py"], cwd=str(d),
                              capture_output=True, text=True, timeout=120)
        shutil.rmtree(d, ignore_errors=True)
        return proc.stdout + proc.stderr

    COMPTE = "PAFACTICE12345"

    @unittest.skipUnless(shutil.which("git"), "git absent")
    def test_une_cle_dans_un_fichier_source_suivi_bloque(self):
        """La première version du contrôle ne regardait que decision_log.jsonl
        et docs/data.json. Une clé posée dans un .py — le cas qu'il existe pour
        attraper — lui aurait échappé."""
        sortie = self._depot_git({"agent.py": "# debug: %s\n" % self.CLE})
        self.assertIn("CONTIENT LA VALEUR DE ALPACA_API_KEY", sortie)
        self.assertIn("agent.py", sortie)

    @unittest.skipUnless(shutil.which("git"), "git absent")
    def test_un_numero_de_compte_alerte_sans_bloquer(self):
        """Deux sévérités : un numéro de compte n'autorise aucune action sans
        les clés, et le tableau de bord publie déjà celui du compte courant.
        Crier au même volume que pour une clé apprendrait à ignorer les deux."""
        sortie = self._depot_git({"notes.md": "compte %s\n" % self.COMPTE})
        self.assertIn("contient la valeur de ALPACA_ACCOUNT_ID", sortie)
        self.assertNotIn("CONTIENT LA VALEUR DE ALPACA_ACCOUNT_ID", sortie,
                         "un numéro de compte bloque comme une clé")

    @unittest.skipUnless(shutil.which("git"), "git absent")
    def test_un_fichier_NON_suivi_n_est_pas_signale(self):
        """Un brouillon local qui ne partira jamais sur le dépôt n'a pas à
        bloquer un commit. Sans ce contrôle, le balayage crierait sur des
        fichiers de travail et on apprendrait à l'ignorer."""
        import garde_fou
        d = Path(tempfile.mkdtemp(prefix="hindsight-nonsuivi-"))
        try:
            shutil.copy(Path(garde_fou.__file__).resolve().parent / "garde_fou.py",
                        d / "garde_fou.py")
            (d / ("." + "env")).write_text("ALPACA_API_KEY=%s\n" % self.CLE,
                                           encoding="utf-8")
            subprocess.run([GIT, "init", "-q", "."], cwd=str(d),
                           capture_output=True, timeout=30)
            subprocess.run([GIT, "add", "garde_fou.py"], cwd=str(d),
                           capture_output=True, timeout=30)
            # ecrit APRES le `git add` : jamais suivi
            (d / "brouillon.txt").write_text("cle=%s\n" % self.CLE,
                                             encoding="utf-8")
            proc = subprocess.run([sys.executable, "garde_fou.py"], cwd=str(d),
                                  capture_output=True, text=True, timeout=120)
            sortie = proc.stdout + proc.stderr
        finally:
            shutil.rmtree(d, ignore_errors=True)
        self.assertNotIn("brouillon.txt", sortie)

    @unittest.skipUnless(shutil.which("git"), "git absent")
    def test_un_identifiant_factice_ne_declenche_rien(self):
        """Trouvé par la reproduction de l'environnement CI, juste après avoir
        élargi le contrôle à tous les fichiers suivis.

        Les fichiers de test posent eux-mêmes des identifiants factices
        (« cle-de-test », « secret-de-test »). Quand garde_fou tourne avec ces
        valeurs dans l'environnement — ce que fait la suite — il les retrouvait
        dans les sources et BLOQUAIT. Un contrôle qui crie sur des valeurs bidon
        apprend à être ignoré, et c'est le pire sort pour celui-ci."""
        import garde_fou
        d = Path(tempfile.mkdtemp(prefix="hindsight-factice-"))
        try:
            shutil.copy(Path(garde_fou.__file__).resolve().parent / "garde_fou.py",
                        d / "garde_fou.py")
            (d / ("." + "env")).write_text(
                "ALPACA_API_KEY=cle-de-test\nALPACA_SECRET_KEY=secret-de-test\n",
                encoding="utf-8")
            (d / "notes.md").write_text(
                "les tests utilisent cle-de-test et secret-de-test\n",
                encoding="utf-8")
            for args in (["init", "-q", "."], ["add", "-A"]):
                subprocess.run([GIT] + args, cwd=str(d), capture_output=True,
                               timeout=30)
            proc = subprocess.run([sys.executable, "garde_fou.py"], cwd=str(d),
                                  capture_output=True, text=True, timeout=120)
            sortie = proc.stdout + proc.stderr
        finally:
            shutil.rmtree(d, ignore_errors=True)
        self.assertNotIn("CONTIENT LA VALEUR", sortie,
                         "un identifiant factice fait bloquer le garde-fou")

    def test_un_numero_de_compte_reel_reste_detecte_malgre_le_filtre(self):
        """Le filtre anti-remplissage a d'abord utilisé un seuil UNIQUE à 16
        caractères. Il laissait passer les clés (20 et 40) mais rejetait le
        numéro de compte, qui n'en fait que 12 : la détection du numéro avait
        disparu sans bruit. Trois formats ne se filtrent pas avec un seul
        nombre."""
        import garde_fou
        source = (Path(garde_fou.__file__).resolve().parent
                  / "garde_fou.py").read_text(encoding="utf-8")
        self.assertIn("ALPACA_ACCOUNT_ID", source)
        self.assertIn("nom == \"ALPACA_ACCOUNT_ID\"", source,
                      "le filtre ne distingue plus le numéro de compte des "
                      "clés : un seuil unique le rejetterait")

    @unittest.skipUnless(shutil.which("git"), "git absent")
    def test_une_cle_retiree_des_fichiers_reste_vue_dans_l_historique(self):
        """Tout le reste du contrôle regarde les fichiers TELS QU'ILS SONT. Une
        clé committée puis retirée n'y apparaît plus — et reste dans
        l'historique public pour toujours.

        Le chemin : `git commit --no-verify` contourne le hook, donc contourne
        tout le garde-fou. Sans ce balayage, la fuite serait DÉFINITIVEMENT
        silencieuse.

        Vérifié une fois sur le vrai dépôt, 87 commits : aucune clé, aucun
        secret n'a jamais été committé. Ce contrôle existe pour que ça le
        reste."""
        import garde_fou
        d = Path(tempfile.mkdtemp(prefix="hindsight-histo-"))
        try:
            shutil.copy(Path(garde_fou.__file__).resolve().parent / "garde_fou.py",
                        d / "garde_fou.py")
            (d / ("." + "env")).write_text("ALPACA_API_KEY=%s\n" % self.CLE,
                                           encoding="utf-8")
            # Le fichier d'environnement doit etre IGNORE, comme dans le vrai
            # depot. Sans ca, `git add -A` le committe et la cle se retrouve
            # dans l'historique par ce chemin-la : le test « historique propre »
            # echouait, et le test « cle retiree » passait pour la MAUVAISE
            # raison -- il verifiait un fichier d'environnement commite, pas
            # une cle retiree d'un fichier source.
            (d / ".gitignore").write_text("." + "env\n", encoding="utf-8")
            for args in (["init", "-q", "."], ["config", "user.email", "t@t"],
                         ["config", "user.name", "t"]):
                subprocess.run([GIT] + args, cwd=str(d), capture_output=True,
                               timeout=30)
            # commit fautif, puis retrait du fichier
            (d / "notes.md").write_text("cle: %s\n" % self.CLE, encoding="utf-8")
            subprocess.run([GIT, "add", "-A"], cwd=str(d), capture_output=True,
                           timeout=30)
            subprocess.run([GIT, "commit", "-qm", "fautif", "--no-verify"],
                           cwd=str(d), capture_output=True, timeout=30)
            (d / "notes.md").unlink()
            subprocess.run([GIT, "add", "-A"], cwd=str(d), capture_output=True,
                           timeout=30)
            subprocess.run([GIT, "commit", "-qm", "retire", "--no-verify"],
                           cwd=str(d), capture_output=True, timeout=30)

            restants = [f for f in d.rglob("*")
                        if f.is_file() and ".git" not in f.parts
                        and "env" not in f.name
                        and self.CLE in f.read_text(encoding="utf-8",
                                                    errors="replace")]
            self.assertEqual(restants, [],
                             "prérequis : la clé ne doit plus être dans aucun "
                             "fichier, sinon ce test vérifie le mauvais chemin")

            proc = subprocess.run([sys.executable, "garde_fou.py"], cwd=str(d),
                                  capture_output=True, text=True, timeout=180)
            sortie = proc.stdout + proc.stderr
        finally:
            shutil.rmtree(d, ignore_errors=True)

        self.assertIn("APPARAIT DANS L'HISTORIQUE", sortie,
                      "une clé committée puis retirée n'est plus vue par "
                      "personne, et reste récupérable par quiconque clone")
        self.assertIn("REVOQUER", sortie,
                      "le message doit dire que la révocation est le SEUL "
                      "remède : ce projet s'interdit de réécrire l'historique, "
                      "donc retirer la ligne ne répare rien")

    @unittest.skipUnless(shutil.which("git"), "git absent")
    def test_un_historique_propre_ne_declenche_rien(self):
        """Contrôle : sans lui, bloquer TOUJOURS passerait le test du dessus."""
        import garde_fou
        d = Path(tempfile.mkdtemp(prefix="hindsight-histo-ok-"))
        try:
            shutil.copy(Path(garde_fou.__file__).resolve().parent / "garde_fou.py",
                        d / "garde_fou.py")
            (d / ("." + "env")).write_text("ALPACA_API_KEY=%s\n" % self.CLE,
                                           encoding="utf-8")
            (d / "notes.md").write_text("rien de sensible ici\n", encoding="utf-8")
            # Le fichier d'environnement doit etre IGNORE, comme dans le vrai
            # depot. Sans ca, `git add -A` le committe et la cle se retrouve
            # dans l'historique par ce chemin-la : le test « historique propre »
            # echouait, et le test « cle retiree » passait pour la MAUVAISE
            # raison -- il verifiait un fichier d'environnement commite, pas
            # une cle retiree d'un fichier source.
            (d / ".gitignore").write_text("." + "env\n", encoding="utf-8")
            for args in (["init", "-q", "."], ["config", "user.email", "t@t"],
                         ["config", "user.name", "t"], ["add", "-A"],
                         ["commit", "-qm", "propre", "--no-verify"]):
                subprocess.run([GIT] + args, cwd=str(d), capture_output=True,
                               timeout=30)
            proc = subprocess.run([sys.executable, "garde_fou.py"], cwd=str(d),
                                  capture_output=True, text=True, timeout=180)
            sortie = proc.stdout + proc.stderr
        finally:
            shutil.rmtree(d, ignore_errors=True)
        self.assertNotIn("APPARAIT DANS L'HISTORIQUE", sortie)

    def test_des_fichiers_propres_ne_declenchent_rien(self):
        """Contrôle : sans lui, bloquer TOUJOURS passerait les deux tests
        ci-dessus."""
        sortie = self._verdict(
            contenu_journal='{"outcome":"no_edge","reason":"rien a signaler"}\n',
            contenu_data='{"account":{"equity":"100000"}}')
        self.assertNotIn("CONTIENT LA VALEUR", sortie)


@unittest.skipUnless(sys.platform == "darwin", "pmset n'existe que sur macOS")
class TestReveilProgramme(unittest.TestCase):
    """Le README raconte un incident RÉEL : le moniteur de sorties a échoué 11
    fois de suite un après-midi. Le Mac dormait, et launchd ne déclenchait le
    job que pendant de brefs réveils de maintenance — trop courts pour que le
    Wi-Fi se reconnecte avant que l'appel réseau expire.

    Le remède tient en une ligne, écrite dans le README, qui demande le mot de
    passe administrateur — donc elle ne peut pas être automatisée. Et RIEN ne
    vérifiait qu'elle ait été lancée. Mesuré le 27/08 sur cette machine :
    aucun événement récurrent programmé.

    Le plist market-hours-awake garde la machine ÉVEILLÉE, mais son propre
    commentaire le dit : « It can only keep the machine awake — it CANNOT wake
    a machine that is already asleep. » Les deux sont nécessaires, un seul
    était vérifiable.

    On teste en fabriquant un faux `pmset` : c'est le vrai chemin du contrôle,
    subprocess compris, pas sa logique isolée.
    """

    RACINE = Path(__file__).resolve().parent

    SORTIE_SANS = ("Scheduled power events:\n"
                   " [0]  wake at 08/26/2026 17:04:22 by 'com.apple.alarm'\n")
    SORTIE_AVEC = (SORTIE_SANS + "Repeating power events:\n"
                   "  wakeorpoweron at 3:15PM every Monday,Tuesday,Wednesday,"
                   "Thursday,Friday\n")

    def _sortie(self, sortie_pmset, code=0, env_ci=False):
        d = Path(tempfile.mkdtemp(prefix="hindsight-pmset-"))
        try:
            shutil.copy(self.RACINE / "garde_fou.py", d / "garde_fou.py")
            faux = d / "bin"
            faux.mkdir()
            (faux / "pmset").write_text(
                "#!/bin/sh\ncat <<'EOF'\n%s\nEOF\nexit %d\n"
                % (sortie_pmset, code), encoding="utf-8")
            (faux / "pmset").chmod(0o755)
            env = dict(os.environ)
            env.pop("GITHUB_ACTIONS", None)
            env.pop("CI", None)
            if env_ci:
                env["GITHUB_ACTIONS"] = "true"
            env["PATH"] = "%s:%s" % (faux, env.get("PATH", ""))
            proc = subprocess.run([sys.executable, "garde_fou.py"], cwd=str(d),
                                  capture_output=True, text=True, timeout=120,
                                  env=env)
            return proc.stdout + proc.stderr
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_aucun_reveil_recurrent_est_signale(self):
        sortie = self._sortie(self.SORTIE_SANS)
        self.assertIn("AUCUN REVEIL RECURRENT", sortie,
                      "le mécanisme qui fait tenir la surveillance non "
                      "surveillée est absent et rien ne le dit")
        self.assertIn("sudo pmset repeat wakeorpoweron", sortie,
                      "l'alerte ne donne pas la commande qui corrige")

    def test_un_reveil_recurrent_ne_declenche_rien(self):
        """Contrôle : sans lui, alerter TOUJOURS passerait le test du dessus."""
        self.assertNotIn("AUCUN REVEIL RECURRENT", self._sortie(self.SORTIE_AVEC))

    def test_un_pmset_qui_echoue_avoue_n_avoir_rien_verifie(self):
        """Une sortie vide est indistinguable d'une machine bien programmée :
        ne pas pouvoir vérifier n'est pas la preuve que tout va bien."""
        sortie = self._sortie("", code=1)
        self.assertIn("n'a PAS ete verifie", sortie)

    def test_la_CI_ne_recoit_pas_cette_alerte(self):
        """pmset n'a aucun sens sur un runner Linux, et alerter à chaque run
        apprendrait à ignorer les 🟡."""
        self.assertNotIn("REVEIL", self._sortie(self.SORTIE_SANS, env_ci=True))


@unittest.skipUnless(shutil.which("git"), "git absent")
class TestRenvoisResolvent(unittest.TestCase):
    """Un juge qui suit un renvoi vers un fichier absent ne voit pas une
    coquille : il voit un dossier qui parle de choses qui n'y sont pas.

    Ce n'est pas théorique. Une session antérieure a trouvé 37 renvois morts
    dans ce dépôt, dont un qui disait littéralement au jury d'aller consulter
    les `BRIEF_*.md` « at the repo root » — alors qu'ils venaient d'être
    retirés du suivi git. Le fichier existait encore sur la machine de
    l'auteur ; il n'existait plus pour personne d'autre.
    """

    RACINE = Path(__file__).resolve().parent

    def _sortie(self, readme, gitignore="", fichiers=()):
        import garde_fou
        d = Path(tempfile.mkdtemp(prefix="hindsight-renvois-"))
        try:
            shutil.copy(self.RACINE / "garde_fou.py", d / "garde_fou.py")
            (d / "README.md").write_text(readme, encoding="utf-8")
            if gitignore:
                (d / ".gitignore").write_text(gitignore, encoding="utf-8")
            for nom in fichiers:
                (d / nom).write_text("x\n", encoding="utf-8")
            for args in (["init", "-q", "."], ["add", "-A"]):
                subprocess.run([shutil.which("git")] + args, cwd=str(d),
                               capture_output=True, timeout=30)
            proc = subprocess.run([sys.executable, "garde_fou.py"], cwd=str(d),
                                  capture_output=True, text=True, timeout=120)
            return proc.stdout + proc.stderr
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_un_renvoi_vers_un_fichier_absent_est_signale(self):
        sortie = self._sortie("Voir `NOTES_INTERNES.md` pour le detail.\n")
        self.assertIn("NOTES_INTERNES.md", sortie)
        self.assertIn("que le depot ne contient pas", sortie)

    def test_un_motif_a_etoile_sans_correspondance_est_signale(self):
        """La forme EXACTE du renvoi mort d'origine. Une simple vérification
        d'existence de chemin ne l'aurait pas attrapé : `BRIEF_*.md` n'est pas
        un chemin, c'est un motif."""
        sortie = self._sortie("See the `BRIEF_*.md` files at the repo root.\n")
        self.assertIn("BRIEF_*.md", sortie)

    def test_un_motif_a_etoile_qui_correspond_ne_declenche_rien(self):
        sortie = self._sortie("See the `BRIEF_*.md` files.\n",
                              fichiers=("BRIEF_sprint.md",))
        self.assertNotIn("que le depot ne contient pas", sortie)

    def test_un_fichier_gitignore_n_est_pas_un_renvoi_mort(self):
        """LE contrôle qui compte : c'est un clone frais — donc la CI — qui a
        montré le défaut. La première version acceptait aussi os.path.exists,
        donc elle passait sur la machine de l'auteur (où state.json existe,
        généré à l'exécution) et CRIAIT sur un clone. Un contrôle qui crie à
        chaque run de CI est un contrôle qu'on apprend à ignorer.

        Un fichier gitignoré est absent du clone PAR CONSTRUCTION : le README
        le décrit comme créé au vol, pas comme livré."""
        sortie = self._sortie("L'agent écrit `state.json` à l'exécution.\n",
                              gitignore="state.json\n")
        self.assertNotIn("state.json", sortie)

    def test_un_fichier_suivi_ne_declenche_rien(self):
        """Contrôle : sans lui, tout signaler passerait les tests ci-dessus."""
        sortie = self._sortie("Voir `agent.py` pour la boucle.\n",
                              fichiers=("agent.py",))
        self.assertNotIn("que le depot ne contient pas", sortie)

    def test_le_depot_reel_n_a_aucun_renvoi_mort(self):
        """Sur le vrai dépôt, tel qu'il est aujourd'hui."""
        import garde_fou
        avant = len(garde_fou.alertes)
        try:
            garde_fou.controle_renvois_resolvent()
            morts = [a for a in garde_fou.alertes[avant:]
                     if "ne contient pas" in a[1]]
        finally:
            del garde_fou.alertes[avant:]
        self.assertEqual(morts, [], "le dépôt cite des fichiers qu'il ne "
                                    "contient pas : %s" % morts)


class TestCompatibiliteFuture(unittest.TestCase):
    """Le workflow CI demande `python-version: "3.x"` — la DERNIÈRE version
    disponible. Toute cette suite n'a jamais tourné que sur le Python 3.9 de la
    machine de développement, et aucun autre interpréteur n'y est installé.

    La vérification s'est donc faite en cherchant les constructions dont le
    comportement diffère entre versions, pas en exécutant. Ces tests figent ce
    qui a été trouvé, pour que la dérive ne se reproduise pas en silence.
    """

    RACINE = Path(__file__).resolve().parent

    def _modules(self):
        return sorted(self.RACINE.glob("*.py"))

    def test_aucune_sequence_d_echappement_invalide(self):
        """`"\\d"` dans une chaîne non brute est un DeprecationWarning depuis
        3.6, un SyntaxWarning depuis 3.12, et c'est destiné à devenir une
        ERREUR DE SYNTAXE.

        Trouvé le 27/08 en lançant la suite avec -W error::DeprecationWarning :
        une docstring de ce fichier même contenait `([\\d.]+)` et faisait
        échouer l'import. Sur 3.9 ce n'était qu'un avertissement invisible ; sur
        une version future, le module ne se charge plus du tout."""
        import warnings
        fautifs = []
        for chemin in self._modules():
            with warnings.catch_warnings(record=True) as attrapes:
                warnings.simplefilter("always")
                try:
                    compile(chemin.read_text(encoding="utf-8"), str(chemin), "exec")
                except SyntaxError as err:
                    fautifs.append("%s:%s %s" % (chemin.name, err.lineno, err.msg))
                    continue
                for a in attrapes:
                    if "escape sequence" in str(a.message):
                        fautifs.append("%s:%s %s"
                                       % (chemin.name, a.lineno, a.message))
        self.assertEqual(fautifs, [],
                         "séquence(s) d'échappement invalide(s) : %s — "
                         "avertissement aujourd'hui, erreur de syntaxe demain"
                         % "; ".join(fautifs))

    def _appels_et_imports(self):
        """Les appels et imports REELS de chaque module, via l'arbre syntaxique.

        Ecrit en AST apres que la premiere version, qui cherchait des chaines
        de caracteres, se soit trouvee ELLE-MEME : la liste des noms interdits
        contient les noms interdits, et les docstrings qui expliquent le
        correctif citent l'appel corrige. Deux tests rouges sur un depot sain.

        Un nom cite dans une docstring n'est pas un appel. L'AST le sait, le
        `in` d'une chaine non."""
        import ast
        attributs, imports = [], []
        for chemin in self._modules():
            arbre = ast.parse(chemin.read_text(encoding="utf-8"), str(chemin))
            for n in ast.walk(arbre):
                if isinstance(n, ast.Attribute):
                    attributs.append((chemin.name, n.lineno, n.attr))
                elif isinstance(n, ast.Import):
                    for a in n.names:
                        imports.append((chemin.name, n.lineno, a.name.split(".")[0]))
                elif isinstance(n, ast.ImportFrom) and n.module:
                    imports.append((chemin.name, n.lineno, n.module.split(".")[0]))
        return attributs, imports

    def test_toute_lecture_ecriture_de_texte_precise_son_encodage(self):
        """Sans `encoding=`, Python utilise celui de la LOCALE — donc le même
        code ne lit pas la même chose selon la machine.

        Mesuré le 27/08 : sur macOS, Python rend UTF-8 quoi qu'il arrive, même
        sous `env -i`, même avec LANG=C. Le défaut n'est donc PAS atteignable
        sur la plateforme cible. Mais la CI tourne sur Linux, où LANG=C donne de
        l'ASCII, et un juge qui clone dans un conteneur — où LANG est souvent
        absent — est dans ce cas-là.

        Démontré plutôt qu'affirmé, avec un codec ascii forcé : l'écriture lève
        UnicodeEncodeError sur le premier caractère accentué, la lecture lève
        UnicodeDecodeError sur le même octet. La conséquence porte sur la PREUVE
        PUBLIÉE — log_run() lèverait et l'enregistrement serait perdu du
        fichier, read_log() lèverait et le tableau de bord ne se construirait
        plus.

        Une seule exception, vérifiée par son nom : le descripteur du verrou
        d'état, qui ne sert qu'à flock() et où l'on n'écrit jamais de texte.
        Le préciser suggérerait le contraire."""
        import ast
        fautifs = []
        for chemin in self._modules():
            lignes = chemin.read_text(encoding="utf-8").splitlines()
            for n in ast.walk(ast.parse("\n".join(lignes), str(chemin))):
                if not isinstance(n, ast.Call):
                    continue
                nom = (n.func.id if isinstance(n.func, ast.Name)
                       else getattr(n.func, "attr", None))
                if nom not in ("open", "read_text", "write_text"):
                    continue
                if "encoding" in {k.arg for k in n.keywords}:
                    continue
                # un mode binaire n'a pas d'encodage
                if any(isinstance(a, ast.Constant) and isinstance(a.value, str)
                       and "b" in a.value for a in n.args[1:2]):
                    continue
                # le verrou : flock seulement, jamais de texte
                cible = n.args[0] if n.args else None
                if isinstance(cible, ast.Name) and cible.id == "lock_path":
                    continue
                fautifs.append("%s:%d %s" % (chemin.name, n.lineno,
                                             lignes[n.lineno - 1].strip()[:50]))
        self.assertEqual(fautifs, [],
                         "lecture/écriture de texte sans encoding= : %s — le "
                         "résultat dépendrait alors de la locale de la machine"
                         % "; ".join(fautifs))

    def test_aucun_appel_datetime_utcnow(self):
        """datetime.utcnow() est DEPRECIE depuis 3.12 et sera SUPPRIME. Le jour
        ou il disparait, l'agent ne demarre plus -- pas un avertissement, une
        panne.

        Les trois usages n'extrayaient qu'une DATE UTC, sans arithmetique sur
        les fuseaux : le remplacement par datetime.now(timezone.utc) est
        mecaniquement equivalent, verifie cote a cote."""
        attributs, _ = self._appels_et_imports()
        fautifs = ["%s:%d" % (f, l) for f, l, a in attributs if a == "utcnow"]
        self.assertEqual(fautifs, [],
                         "datetime.utcnow() encore appele : %s"
                         % ", ".join(fautifs))

    def test_aucune_autre_depreciation_connue(self):
        """Les retraits annonces de 3.12/3.13 qui casseraient ce depot."""
        ATTRIBUTS = {"utcfromtimestamp", "getdefaultlocale"}
        MODULES = {"distutils", "pkg_resources", "imp"}
        attributs, imports = self._appels_et_imports()
        fautifs = ["%s:%d %s" % (f, l, a) for f, l, a in attributs
                   if a in ATTRIBUTS]
        fautifs += ["%s:%d import %s" % (f, l, m) for f, l, m in imports
                    if m in MODULES]
        self.assertEqual(fautifs, [], "usage(s) deprecie(s) : %s"
                         % ", ".join(fautifs))



class TestVocabulairePartageAvecLaPage(unittest.TestCase):
    """Ajouté le 27/08. Python invente les valeurs d'`outcome` ; le JavaScript
    de docs/index.html décide de la COULEUR de chacune. Rien ne reliait les
    deux, et la page n'a qu'un repli : `badge-muted`, gris discret.

    Ce n'est pas une inquiétude théorique — la dérive s'est produite trois
    fois, dont deux fois le jour même où ce test a été écrit :
      · `order_status_unknown` (ajouté le 27/08) s'affichait en gris, la
        sévérité exactement inverse de ce que la situation demande ;
      · `interrupted`, né du correctif de ce jour dans monitor_exits.py,
        tombait au même endroit une heure après avoir été créé ;
      · `unknown`, le défaut de naissance des deux modules, n'a jamais eu
        d'entrée du tout.

    Le repli gris est le pire cas possible pour ce genre de dérive : la page
    ne casse pas, n'avertit pas, et rend « rien à signaler » pour un état que
    personne n'a encore pris la peine de qualifier."""

    RACINE = Path(__file__).resolve().parent
    MODULES = ("agent.py", "monitor_exits.py")

    # `"outcome"` est le NOM de la clé, jamais une valeur — il est ramassé par
    # le balayage de `record.get("outcome", "unknown")`. Seule exception, et
    # elle est nommée : une exception muette rendrait ce test vide sans qu'on
    # puisse le voir.
    PAS_UNE_VALEUR = {"outcome"}

    def _outcomes_ecrits_par_python(self):
        """Toute chaîne littérale pouvant atterrir dans un champ `outcome`.

        La PREMIÈRE version de cette extraction ne regardait que les
        affectations à une constante. Elle ratait
        `record["outcome"] = trade_outcomes.pop() if ... else "mixed"` — donc
        `mixed`, et toutes les valeurs propagées depuis les décisions par
        symbole. Un test de couverture bâti sur un instrument lossy annonce
        une couverture qu'il n'a pas ; test_l_extracteur_n_est_pas_lossy
        ci-dessous existe pour que cette régression-là soit visible.

        On balaie donc TOUTE l'expression affectée, ce qui sur-collecte
        légèrement. C'est le bon sens de l'erreur : sur-collecter réclame une
        entrée JS de plus, jamais une de moins."""
        import ast
        trouves = {}
        for nom in self.MODULES:
            chemin = self.RACINE / nom
            arbre = ast.parse(chemin.read_text(encoding="utf-8"), nom)

            def recolter(noeud, ligne):
                for c in ast.walk(noeud):
                    if (isinstance(c, ast.Constant) and isinstance(c.value, str)
                            and c.value not in self.PAS_UNE_VALEUR):
                        trouves.setdefault(c.value, "%s:%d" % (nom, ligne))

            for n in ast.walk(arbre):
                if isinstance(n, ast.Assign):
                    for cible in n.targets:
                        if (isinstance(cible, ast.Subscript)
                                and isinstance(cible.slice, ast.Constant)
                                and cible.slice.value == "outcome"):
                            recolter(n.value, n.lineno)
                elif isinstance(n, ast.Dict):
                    for k, v in zip(n.keys, n.values):
                        if isinstance(k, ast.Constant) and k.value == "outcome":
                            recolter(v, n.lineno)
                elif isinstance(n, ast.Compare):
                    if "'outcome'" in ast.dump(n.left):
                        for c in n.comparators:
                            recolter(c, n.lineno)
        return trouves

    def _ce_que_la_page_sait_rendre(self):
        import re
        page = (self.RACINE / "docs" / "index.html").read_text(encoding="utf-8")
        bloc = page[page.index("const map = {"):]
        bloc = bloc[:bloc.index("};")]
        table = set(re.findall(r"^\s+(\w+):\s*\[", bloc, re.M))
        branches = set(re.findall(r"outcome === '(\w+)'", page))
        return table, branches

    def test_l_extracteur_n_est_pas_lossy(self):
        """Contrôle de l'instrument, pas du code. `mixed` n'est jamais écrit
        littéralement : il naît d'un `IfExp`. S'il disparaît de l'extraction,
        c'est que le test principal a cessé de voir une famille entière de
        valeurs — et il continuerait à passer, vert, en ne vérifiant rien."""
        trouves = self._outcomes_ecrits_par_python()
        self.assertIn("mixed", trouves,
                      "l'extracteur ne voit plus les outcomes affectés par "
                      "autre chose qu'une constante : le test principal est "
                      "devenu vide sans le dire")
        self.assertIn("order_status_unknown", trouves)

    def test_chaque_outcome_ecrit_par_python_a_une_couleur_choisie(self):
        trouves = self._outcomes_ecrits_par_python()
        table, branches = self._ce_que_la_page_sait_rendre()
        orphelins = ["%s (%s)" % (v, ou) for v, ou in sorted(trouves.items())
                     if v not in table and v not in branches]
        self.assertEqual(
            orphelins, [],
            "outcome(s) écrits par Python que docs/index.html ne sait pas "
            "rendre — ils tombent sur le repli `badge-muted`, gris discret, "
            "quelle que soit leur gravité : %s" % ", ".join(orphelins))

    # Champs écrits sur un trade que la page ne rend volontairement PAS.
    # Liste explicite et non vide par principe : le but de ce test n'est pas
    # que tout soit affiché, c'est qu'aucun champ ne cesse de l'être par
    # OUBLI. Y ajouter une entrée est une décision qu'on écrit ; ne rien
    # écrire n'en était pas une.
    NON_RENDUS_VOLONTAIREMENT = {
        # Le symbole du contrat d'option retenu (ex. SPY260831P00764000).
        # Informatif, mais aucune conséquence de sûreté à ne pas l'afficher :
        # la ligne porte déjà le sous-jacent, le sens, la quantité et l'id
        # d'ordre, qui suffisent à retrouver le contrat chez Alpaca.
        "contract",
    }

    def test_chaque_champ_ecrit_sur_un_trade_est_rendu_ou_ecarte_sciemment(self):
        """Trouvé par ce croisement même : `record_order_submitted_failed`
        était écrit par agent.py et n'apparaissait nulle part sur la page.
        Il signifie que l'ordre est parti mais que le garde-fou anti-doublon
        n'a pas pu être armé — le seul état après lequel il ne faut surtout
        pas relancer à l'aveugle. Il rendait exactement la même ligne qu'un
        ordre normal.

        L'extraction gère `AnnAssign` (`trade_record: dict = {...}`), qui est
        la forme réelle de la construction ligne 400. Les trois versions
        précédentes de ce genre d'extracteur, écrites dans la même journée,
        la rataient — et rapportaient `symbol` et `direction` comme jamais
        écrits, ce qui était faux. L'instrument se vérifie ci-dessous."""
        import ast, re
        chemin = self.RACINE / "agent.py"
        arbre = ast.parse(chemin.read_text(encoding="utf-8"), "agent.py")
        cles = {}

        def poser(k, ligne):
            if isinstance(k, ast.Constant):
                cles.setdefault(k.value, ligne)

        for n in ast.walk(arbre):
            if (isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)
                    and n.target.id == "trade_record"
                    and isinstance(n.value, ast.Dict)):
                for k in n.value.keys:
                    poser(k, n.lineno)
            if isinstance(n, ast.Assign):
                for c in n.targets:
                    if (isinstance(c, ast.Name) and c.id == "trade_record"
                            and isinstance(n.value, ast.Dict)):
                        for k in n.value.keys:
                            poser(k, n.lineno)
                    if (isinstance(c, ast.Subscript) and isinstance(c.value, ast.Name)
                            and c.value.id == "trade_record"):
                        poser(c.slice, n.lineno)

        # Contrôle d'instrument : `symbol` n'est écrit QUE par l'AnnAssign de
        # la ligne 400. S'il disparaît, l'extracteur est redevenu lossy et ce
        # test ne vérifie plus grand-chose, en restant vert.
        self.assertIn("symbol", cles,
                      "l'extracteur ne voit plus `trade_record: dict = {...}` "
                      "(AnnAssign) : le test est devenu creux sans le dire")

        page = (self.RACINE / "docs" / "index.html").read_text(encoding="utf-8")
        lus = set(re.findall(r"\bt\.([a-z_]+)", page))
        muets = ["%s (agent.py:%d)" % (k, l) for k, l in sorted(cles.items())
                 if k not in lus and k not in self.NON_RENDUS_VOLONTAIREMENT]
        self.assertEqual(
            muets, [],
            "champ(s) écrits sur un trade que docs/index.html ne lit jamais : "
            "%s — ils arrivent dans data.json et meurent au rendu. Les rendre, "
            "ou les inscrire dans NON_RENDUS_VOLONTAIREMENT avec la raison."
            % ", ".join(muets))

    def test_la_liste_des_ecartes_ne_couvre_pas_des_champs_disparus(self):
        """Une liste d'exceptions qui vieillit devient un trou. Si un champ
        écarté n'est plus écrit du tout, l'entrée doit partir — sinon elle
        couvrirait un jour un homonyme sans que personne ne l'ait voulu."""
        source = (self.RACINE / "agent.py").read_text(encoding="utf-8")
        for champ in self.NON_RENDUS_VOLONTAIREMENT:
            self.assertIn('trade_record["%s"]' % champ, source,
                          "%s est écarté du rendu mais n'est plus écrit par "
                          "agent.py : l'exception a survécu au champ" % champ)

    # Ce que docs/data.json a le droit de publier sous "account". Liste
    # BLANCHE : ce fichier est suivi par git et servi publiquement par GitHub
    # Pages, et il est rempli depuis la réponse BRUTE de l'API Alpaca. Tout
    # champ ajouté au payload d'Alpaca, ou recopié ici sans y penser, part sur
    # un dépôt public à la publication suivante.
    CHAMPS_DE_COMPTE_PUBLIABLES = {
        # L'identifiant « PA... » visible par un humain. Publié DÉLIBÉRÉMENT :
        # c'est celui que le formulaire de soumission réclame, et le tableau
        # de bord l'affiche pour qu'un juge vérifie que cette page correspond
        # bien au compte déclaré. Sans lui, ce recoupement est impossible.
        "account_number",
        "status", "equity", "cash", "buying_power", "portfolio_value",
    }

    def test_data_json_ne_publie_que_les_champs_de_compte_choisis(self):
        """Trouvé le 27/08 en croisant ce que build_snapshot() écrit avec ce
        que la page lit : le champ `id` — l'UUID interne du compte, 36
        caractères — était publié dans un fichier suivi et servi
        publiquement, alors que la page ne le lit QUE comme repli derrière
        `account_number`, toujours présent sur un compte réel. Il n'était
        donc affiché à personne, jamais.

        Il était déjà dans 6 commits poussés au moment de la découverte. Rien
        ne le retire du passé sans réécrire l'historique, ce que ce projet
        s'interdit ; ce test empêche la suite, pas le passé.

        Ni l'UUID ni le numéro de compte n'autorisent quoi que ce soit sans
        les clés — ce sont des identifiants, pas des pouvoirs. Ce qui compte
        ici, c'est qu'un champ soit parti sans que personne ne l'ait décidé :
        le payload d'Alpaca est recopié, et il grandira."""
        import ast
        arbre = ast.parse((self.RACINE / "publish_dashboard.py").read_text(
            encoding="utf-8"), "publish_dashboard.py")
        publies = None
        for n in ast.walk(arbre):
            if isinstance(n, ast.Dict):
                for k, v in zip(n.keys, n.values):
                    if (isinstance(k, ast.Constant) and k.value == "account"
                            and isinstance(v, ast.Dict)):
                        publies = {c.value for c in v.keys
                                   if isinstance(c, ast.Constant)}
        self.assertIsNotNone(
            publies,
            "le bloc \"account\" de build_snapshot() est introuvable : ce "
            "test ne vérifie plus rien (contrôle d'instrument)")
        surplus = sorted(publies - self.CHAMPS_DE_COMPTE_PUBLIABLES)
        self.assertEqual(
            surplus, [],
            "champ(s) de compte publiés dans docs/data.json — fichier suivi "
            "et servi publiquement — sans décision explicite : %s. Les "
            "retirer, ou les inscrire dans CHAMPS_DE_COMPTE_PUBLIABLES avec "
            "la raison." % ", ".join(surplus))

    def test_le_fichier_publie_sur_le_disque_respecte_la_meme_liste(self):
        """Le test ci-dessus lit le CODE. Celui-ci lit le FICHIER réellement
        présent dans docs/, celui que GitHub Pages sert. Les deux peuvent
        diverger : data.json n'est réécrit qu'à la publication suivante, donc
        un champ retiré du code reste sur le disque — et en ligne — jusqu'à
        ce que publish_dashboard.py retourne."""
        import json
        chemin = self.RACINE / "docs" / "data.json"
        if not chemin.exists():
            self.skipTest("docs/data.json absent — rien n'est publié")
        compte = json.loads(chemin.read_text(encoding="utf-8")).get("account", {})
        surplus = sorted(set(compte) - self.CHAMPS_DE_COMPTE_PUBLIABLES)
        self.assertEqual(
            surplus, [],
            "docs/data.json contient sur le disque des champs de compte non "
            "prévus : %s — republier le tableau de bord pour les retirer de "
            "ce qui est servi en ligne" % ", ".join(surplus))

    def test_chaque_issue_de_sortie_est_traitee_par_le_badge(self):
        """Second versant du même pont. risk_gates.ExitKind décide de ce qui
        est arrivé à UNE position ; depuis le correctif du 27/08, c'est cette
        valeur — et non l'`outcome` global — qui donne sa sévérité au badge
        du moniteur. Un `ExitKind` ajouté sans toucher à la page retomberait
        en silence dans la branche finale, celle qui ne tranche pas."""
        import risk_gates
        page = (self.RACINE / "docs" / "index.html").read_text(encoding="utf-8")
        debut = page.index("if (d.run_type === 'exit_monitor') {")
        branche = page[debut:page.index("const map = {", debut)]
        manquants = [k.value for k in risk_gates.ExitKind
                     if ("'%s'" % k.value) not in branche]
        # HOLDING est le seul cas volontairement absent : il n'atteint jamais
        # le journal (voir _merite_le_journal / is_routine), donc aucun badge
        # ne peut le rendre. Nommé plutôt que toléré en silence.
        manquants = [m for m in manquants if m != "holding"]
        self.assertEqual(
            manquants, [],
            "ExitKind non traité par outcomeBadge : %s — la position "
            "correspondante serait rendue sans que sa gravité soit lue"
            % ", ".join(manquants))

if __name__ == "__main__":
    unittest.main(verbosity=2)
