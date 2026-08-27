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
import os
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
