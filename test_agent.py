"""Tests de l'orchestration (agent.py), par opposition aux portes de risque
elles-mêmes (test_risk_gates.py).

Ajouté le 27/08/2026. agent.py n'avait aucune couverture : c'est pourtant lui
qui décide de l'ORDRE des opérations, et l'ordre est ce qui a cassé ici.

Aucun test de ce fichier ne touche le réseau : la frontière alpaca_cli est
entièrement bouchée, et un garde-fou dans setUp fait échouer bruyamment tout
test qui tenterait de l'atteindre.
"""

from __future__ import annotations

import io
import contextlib
import json
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


class BaseAgent(unittest.TestCase):
    EQUITE = 100000.0

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hindsight-agent-"))
        self._sauve = {
            "STATE_FILE": risk_gates.STATE_FILE,
            "LOG_FILE": decision_log.LOG_FILE,
            "run": alpaca_cli.run,
            "require_credentials": config.require_credentials,
            "get_clock": alpaca_cli.get_clock,
            "manage_exits": risk_gates.manage_exits,
            "is_halted": risk_gates.is_halted,
            "get_account": alpaca_cli.get_account,
            "list_open": alpaca_cli.list_open_option_positions,
            "ask": alpaca_cli.get_option_ask_price,
            "contrat": alpaca_cli.find_near_the_money_contract,
            "submit": alpaca_cli.submit_paper_option_order,
            "evaluate_symbol": agent.evaluate_symbol,
        }
        risk_gates.STATE_FILE = self.tmp / "state.json"
        decision_log.LOG_FILE = self.tmp / "decision_log.jsonl"

        def _interdit(*a, **k):
            raise AssertionError(
                "un test a tenté d'atteindre le CLI Alpaca (donc le réseau) : "
                "args=%r. Bouche la fonction concernée dans setUp." % (a,))

        alpaca_cli.run = _interdit
        config.require_credentials = lambda: None
        alpaca_cli.get_clock = lambda: {"is_open": True}
        risk_gates.manage_exits = lambda dry_run=False: []
        risk_gates.is_halted = lambda: (False, "")
        alpaca_cli.get_account = lambda: {
            "id": "compte-test", "equity": str(self.EQUITE),
            "portfolio_value": str(self.EQUITE)}
        self.positions_ouvertes = []
        alpaca_cli.list_open_option_positions = lambda: list(self.positions_ouvertes)
        alpaca_cli.get_option_ask_price = lambda s: 2.80
        alpaca_cli.find_near_the_money_contract = (
            lambda sym, direction, spot=None: sym + "260831C00150000")
        agent.evaluate_symbol = lambda sym, seuil: agent.SymbolVerdict(
            symbol=sym, tradeable=True, reason="stub", direction=1, last_close=100.0)
        self.envoyes = []

    def tearDown(self):
        risk_gates.STATE_FILE = self._sauve["STATE_FILE"]
        decision_log.LOG_FILE = self._sauve["LOG_FILE"]
        alpaca_cli.run = self._sauve["run"]
        config.require_credentials = self._sauve["require_credentials"]
        alpaca_cli.get_clock = self._sauve["get_clock"]
        risk_gates.manage_exits = self._sauve["manage_exits"]
        risk_gates.is_halted = self._sauve["is_halted"]
        alpaca_cli.get_account = self._sauve["get_account"]
        alpaca_cli.list_open_option_positions = self._sauve["list_open"]
        alpaca_cli.get_option_ask_price = self._sauve["ask"]
        alpaca_cli.find_near_the_money_contract = self._sauve["contrat"]
        alpaca_cli.submit_paper_option_order = self._sauve["submit"]
        agent.evaluate_symbol = self._sauve["evaluate_symbol"]
        shutil.rmtree(self.tmp, ignore_errors=True)

    @staticmethod
    def _position(symbole, cout):
        return {"symbol": symbole, "asset_class": "us_option",
                "cost_basis": str(cout), "unrealized_plpc": "0.0", "qty": "1"}

    def _soumission(self, expire_pour=()):
        """Boucle la soumission. Les symboles cités dans `expire_pour` lèvent
        TimeoutExpired APRÈS avoir été comptés comme réellement envoyés — c'est
        tout le sujet : l'ordre part, la réponse n'arrive pas."""
        def submit(contract, qty=1):
            self.envoyes.append((contract, qty))
            if any(contract.startswith(s) for s in expire_pour):
                raise subprocess.TimeoutExpired(
                    cmd=["alpaca", "order", "submit"], timeout=30)
            return "id-%d" % len(self.envoyes)
        alpaca_cli.submit_paper_option_order = submit

    def _lance(self, symboles):
        args = types.SimpleNamespace(
            symbols=",".join(symboles), dry_run=False,
            sharpe_threshold=0.0, skip_market_check=False)
        record = {"dry_run": False, "symbols": list(symboles), "outcome": "unknown"}
        with contextlib.redirect_stdout(io.StringIO()):
            agent._run(args, list(symboles), record)
        return record

    def _etat(self):
        if not risk_gates.STATE_FILE.exists():
            return {}
        return json.loads(risk_gates.STATE_FILE.read_text(encoding="utf-8"))

    def _trade(self, record, symbole):
        for t in record.get("trades", []):
            if t["symbol"] == symbole:
                return t
        self.fail("aucun enregistrement de trade pour %s" % symbole)


class TestOrdreAuSortInconnu(BaseAgent):
    """alpaca_cli.run() passe timeout=30 à subprocess.run(). Un dépassement de
    délai ne dit pas que l'ordre a échoué — il dit qu'on ne sait pas. L'ordre
    peut être parti et vivre chez Alpaca pendant que le CLI tarde.

    Avant le 27/08, TimeoutExpired tombait dans le `except Exception` général
    de la boucle d'entrée, qui imprime « skipping this symbol today ». Mesuré :
    traded_today ne contenait pas le symbole (garde anti-doublon désarmé, donc
    une ré-exécution le même jour pouvait doubler l'ordre) et l'argent engagé
    n'entrait pas dans les accumulateurs (le symbole suivant était dimensionné
    comme si la position n'existait pas).
    """

    def test_le_garde_anti_doublon_est_arme_malgre_le_timeout(self):
        self._soumission(expire_pour=("AAA",))
        self._lance(["AAA", "BBB"])
        symboles = self._etat().get("traded_today", {}).get("symbols", [])
        self.assertIn("AAA", symboles,
                      "un ordre a pu partir pour AAA et le garde anti-doublon "
                      "n'est pas armé : une ré-exécution aujourd'hui peut "
                      "soumettre un second ordre sur le même sous-jacent")

    def test_l_argent_engage_compte_pour_le_symbole_suivant(self):
        """Le témoin serré : les positions déjà ouvertes remplissent le plafond
        au point qu'après AAA il ne reste pas de quoi payer un contrat. Avant
        correctif, BBB passait quand même."""
        self.positions_ouvertes = [self._position("ZZZ", 1900.0)]
        self._soumission(expire_pour=("AAA",))
        record = self._lance(["AAA", "BBB"])
        self.assertEqual(self._trade(record, "BBB")["outcome"], "risk_gate_blocked",
                         "BBB a été dimensionné comme si l'ordre AAA — parti, mais "
                         "sans réponse — n'avait engagé aucun argent")

    def test_l_etat_inconnu_est_nomme_et_non_confondu_avec_une_erreur(self):
        self._soumission(expire_pour=("AAA",))
        record = self._lance(["AAA"])
        self.assertEqual(self._trade(record, "AAA")["outcome"], "order_status_unknown")

    def test_je_ne_sais_pas_prime_sur_ca_a_marche(self):
        """Sans préséance, le succès de BBB masquerait sur le tableau de bord
        le seul ordre qu'il faut aller vérifier à la main."""
        self._soumission(expire_pour=("AAA",))
        record = self._lance(["AAA", "BBB"])
        self.assertEqual(self._trade(record, "BBB")["outcome"], "order_submitted",
                         "prérequis du test : BBB doit avoir réussi")
        self.assertEqual(record["outcome"], "order_status_unknown",
                         "la run est résumée par le succès de BBB, ce qui cache "
                         "l'ordre AAA au sort inconnu")

    def test_le_tableau_de_bord_affiche_cet_etat_en_rouge(self):
        """Le fallback de outcomeBadge() rend tout état inconnu en gris discret
        — la sévérité inverse de celle qu'il faut ici."""
        page = (Path(__file__).resolve().parent / "docs" / "index.html").read_text(
            encoding="utf-8")
        # assertTrue et non assertIn : assertIn imprime la MEILLEURE des deux
        # chaines en cas d'echec, ici les 40 Ko de la page entiere -- un rapport
        # illisible pour une assertion d'une ligne.
        self.assertTrue("order_status_unknown: ['badge-red'" in page,
                        "docs/index.html n'a pas de badge rouge pour "
                        "order_status_unknown : le fallback de outcomeBadge() "
                        "l'afficherait en gris discret")

    def test_le_detail_par_symbole_dit_quoi_faire(self):
        """Le badge de la run est rouge, mais c'est la ligne PAR SYMBOLE qui dit
        de quel symbole il s'agit. Sans branche dédiée, renderTrade() tombait
        dans son repli et affichait la chaîne machine « order_status_unknown »
        au lieu d'une instruction."""
        page = (Path(__file__).resolve().parent / "docs" / "index.html").read_text(
            encoding="utf-8")
        self.assertTrue("t.outcome === 'order_status_unknown'" in page,
                        "renderTrade() n'a pas de branche pour "
                        "order_status_unknown : la ligne par symbole afficherait "
                        "la chaîne machine")
        self.assertTrue("ORDER MAY HAVE BEEN SUBMITTED" in page,
                        "la ligne par symbole ne dit pas quoi faire")

    def test_une_soumission_normale_n_est_pas_affectee(self):
        """Contrôle : sans lui, tout marquer « inconnu » passerait les tests
        ci-dessus."""
        self._soumission(expire_pour=())
        record = self._lance(["AAA", "BBB"])
        self.assertEqual(record["outcome"], "order_submitted")
        for s in ("AAA", "BBB"):
            self.assertEqual(self._trade(record, s)["outcome"], "order_submitted")


class TestRefusAuDemarrage(unittest.TestCase):
    """config.require_credentials() signale son refus avec sys.exit(), donc
    lève SystemExit — une BaseException que `except Exception` NE RATTRAPE PAS.

    Mesuré le 27/08, identifiants absents :
      agent.py         -> journal écrit avec outcome='unknown', error=None,
                          rendu en gris discret par outcomeBadge
      monitor_exits.py -> RIEN : ni decision_log.jsonl, ni monitor_last_run.json

    Le second est le plus grave. Le moniteur est la seule protection d'une
    position ouverte, il tourne toutes les 15 minutes sans surveillance, et son
    require_credentials() était appelé AVANT le try — donc le `finally` entier
    était sauté. Le tableau de bord ne pouvait que constater un silence qui
    vieillit, sans jamais pouvoir dire pourquoi.
    """

    MESSAGE = "Missing ALPACA_API_KEY / ALPACA_SECRET_KEY."

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hindsight-demarrage-"))
        self._log = decision_log.LOG_FILE
        self._req = config.require_credentials
        self._argv = list(sys.argv)
        decision_log.LOG_FILE = self.tmp / "decision_log.jsonl"

        def refuse():
            raise SystemExit(self.MESSAGE)

        config.require_credentials = refuse

    def tearDown(self):
        decision_log.LOG_FILE = self._log
        config.require_credentials = self._req
        sys.argv = self._argv
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _dernier_enregistrement(self):
        self.assertTrue(decision_log.LOG_FILE.exists(),
                        "aucune entrée de journal : l'échec est totalement muet")
        lignes = [l for l in decision_log.LOG_FILE.read_text(
            encoding="utf-8").splitlines() if l.strip()]
        return json.loads(lignes[-1])

    def test_agent_nomme_le_refus(self):
        sys.argv = ["agent.py", "--symbols", "SPY"]
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                agent.main()
        rec = self._dernier_enregistrement()
        self.assertEqual(rec.get("outcome"), "error",
                         "un refus de démarrage est journalisé 'unknown' : "
                         "l'entrée ne dit rien de ce qui s'est passé")
        self.assertIn(self.MESSAGE, rec.get("error") or "")

    def test_le_moniteur_ne_meurt_plus_en_silence(self):
        import monitor_exits
        vrai_statut = monitor_exits.MONITOR_STATUS_FILE
        vrai_dedup = monitor_exits.DEDUP_FILE
        monitor_exits.MONITOR_STATUS_FILE = self.tmp / "monitor_last_run.json"
        monitor_exits.DEDUP_FILE = self.tmp / "dedup.json"
        sys.argv = ["monitor_exits.py"]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit):
                    monitor_exits.main()
            rec = self._dernier_enregistrement()
            self.assertEqual(rec.get("outcome"), "error")
            self.assertIn(self.MESSAGE, rec.get("error") or "")

            self.assertTrue(monitor_exits.MONITOR_STATUS_FILE.exists(),
                            "monitor_last_run.json non écrit : la bannière de "
                            "santé attendra 45 minutes pour signaler un jaune "
                            "vague au lieu d'un rouge immédiat")
            statut = json.loads(monitor_exits.MONITOR_STATUS_FILE.read_text(
                encoding="utf-8"))
            self.assertEqual(statut.get("outcome"), "error")
        finally:
            monitor_exits.MONITOR_STATUS_FILE = vrai_statut
            monitor_exits.DEDUP_FILE = vrai_dedup

    def test_une_sortie_propre_n_est_pas_maquillee_en_erreur(self):
        """Contrôle : sans lui, marquer TOUTE SystemExit comme une erreur
        passerait les deux tests ci-dessus. `--help` sort avec le code 0."""
        def sortie_propre():
            raise SystemExit(0)
        config.require_credentials = sortie_propre
        sys.argv = ["agent.py", "--symbols", "SPY"]
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                agent.main()
        rec = self._dernier_enregistrement()
        self.assertNotEqual(rec.get("outcome"), "error",
                            "une sortie de code 0 est maquillée en erreur")


class TestAgentsPlanifies(unittest.TestCase):
    """Les plists de launchagents/ sont du code livré : ils décident de ce que
    la machine fait toute seule, sans personne devant l'écran.

    Trouvé le 27/08 : com.hindsightalpha.publish-dashboard.plist passait
    `--git-push`, soit un `git push` automatique jusqu'à 75 fois par jour.
    publish_dashboard.py dit pourtant l'inverse dans son propre docstring —
    « pushing to the public repo [...] needs an explicit decision each time,
    not a silent default in a script ». Et `git push` pousse TOUTE la branche,
    donc tout commit en cours part avec.
    """

    RACINE = Path(__file__).resolve().parent

    def _plists(self):
        dossier = self.RACINE / "launchagents"
        fichiers = sorted(dossier.glob("*.plist"))
        self.assertTrue(fichiers, "aucun plist trouvé dans launchagents/")
        return fichiers

    def test_aucun_agent_ne_pousse_automatiquement(self):
        fautifs = []
        for f in self._plists():
            for ligne in f.read_text(encoding="utf-8").splitlines():
                nu = ligne.strip()
                if nu.startswith("<!--") or nu.startswith("--"):
                    continue          # une mention en commentaire est la trace
                                      # du retrait, pas un argument actif
                if "<string>--git-push</string>" == nu:
                    fautifs.append(f.name)
        self.assertEqual(fautifs, [],
                         "un agent planifié passe --git-push : la machine "
                         "publierait sur le dépôt public sans décision "
                         "humaine, contre la règle écrite dans "
                         "publish_dashboard.py")

    def test_la_regle_est_toujours_ecrite_dans_le_module(self):
        """Si quelqu'un retire cette phrase du docstring, le test ci-dessus
        continue de passer mais ne défend plus rien de déclaré. On verrouille
        les deux ensemble."""
        source = (self.RACINE / "publish_dashboard.py").read_text(encoding="utf-8")
        self.assertIn("needs an explicit decision each time", source)

    def test_les_agents_qui_lancent_nos_scripts_fixent_leur_repertoire(self):
        """publish_dashboard.git_publish() utilise des chemins RELATIFS et ne
        passe pas de cwd à subprocess : sans WorkingDirectory, git opérerait
        sur le dépôt du répertoire courant, quel qu'il soit.

        La règle ne vaut QUE pour les plists qui lancent un script de ce
        dépôt. market-hours-awake lance /usr/bin/caffeinate avec des arguments
        entièrement absolus et n'a aucun répertoire de travail à fixer —
        l'exiger de lui serait une assertion qui dépasse sa cible, et un test
        qui dépasse sa cible finit par être assoupli plutôt que corrigé."""
        for f in self._plists():
            contenu = f.read_text(encoding="utf-8")
            if ".py</string>" not in contenu:
                continue
            with self.subTest(plist=f.name):
                # assertTrue et non assertIn : assertIn imprimerait le plist
                # entier dans le rapport d'échec.
                self.assertTrue(
                    "<key>WorkingDirectory</key>" in contenu,
                    "%s lance un script du dépôt sans fixer WorkingDirectory" % f.name)


class TestGardeFouMordVraiment(unittest.TestCase):
    """garde_fou.py est lancé par le hook de commit ET par la CI. CLAUDE.md le
    présente comme LE mécanisme qui garantit le paper-trading. Ce test vérifie
    qu'il attrape vraiment ce qu'il annonce, en cassant le dossier pour de bon.

    Trouvé le 27/08 : son contrôle « garde live-trading » cherchait deux
    CHAÎNES dans config.py — « ALPACA_LIVE_TRADE » quelque part, et
    « sys.exit( » quelque part. Mesuré par mutation :

      - bloc `if not PAPER: sys.exit(...)` entièrement supprimé -> code 0
      - `env.pop("ALPACA_LIVE_TRADE", None)` supprimé de cli_env() -> code 0

    La seconde est la protection RÉELLE (le CLI ne peut pas voir une variable
    absente). Le contrôle n'attrapait ni l'une ni l'autre. Un contrôle qui
    n'attrape pas ce qu'il annonce est pire qu'un contrôle absent : il rassure.

    C'est la discipline appliquée partout ailleurs dans ce dépôt — un contrôle
    qui reste vert quand on retire la protection ne prouve rien — appliquée au
    contrôle lui-même.
    """

    RACINE = Path(__file__).resolve().parent
    MSG_REFUS = "ne refuse PAS de"
    MSG_FUITE = "laisse ALPACA_LIVE_TRADE atteindre le CLI"

    def _dossier(self):
        d = Path(tempfile.mkdtemp(prefix="hindsight-gardefou-"))
        for nom in ("config.py", "garde_fou.py"):
            shutil.copy(self.RACINE / nom, d / nom)
        return d

    def _verdict(self, dossier):
        proc = subprocess.run(
            [sys.executable, "garde_fou.py"], cwd=str(dossier),
            capture_output=True, text=True, timeout=120)
        return proc.stdout + proc.stderr

    def _muter(self, dossier, motif, remplacement, etiquette):
        """Applique la mutation ET vérifie qu'elle a bien atterri — une
        mutation qui n'a pas pris rend un « le contrôle mord » gratuit."""
        chemin = dossier / "config.py"
        avant = chemin.read_text(encoding="utf-8")
        apres = re.sub(motif, remplacement, avant, flags=re.M)
        self.assertNotEqual(
            avant, apres,
            "la mutation %r n'a rien changé : config.py a changé de forme et ce "
            "test ne vérifie plus rien." % etiquette)
        chemin.write_text(apres, encoding="utf-8")

    def test_un_dossier_sain_ne_declenche_pas_ce_controle(self):
        """Contrôle : sans lui, un contrôle qui crie TOUJOURS passerait les
        deux tests ci-dessous."""
        sortie = self._verdict(self._dossier())
        self.assertNotIn(self.MSG_REFUS, sortie)
        self.assertNotIn(self.MSG_FUITE, sortie)
        self.assertNotIn("n'a PAS pu être vérifié", sortie,
                         "la sonde de comportement n'a pas pu tourner : le "
                         "contrôle retombe sur ses vérifications textuelles")

    def test_supprimer_le_refus_de_demarrer_est_attrape(self):
        d = self._dossier()
        self._muter(d, r"^    if not PAPER:\n(?:        .*\n|\n)*?(?=\n{0,2}(?:def |\Z))",
                    "\n", "retrait du refus paper/live")
        self.assertIn(self.MSG_REFUS, self._verdict(d),
                      "le refus de démarrer a été supprimé et garde_fou.py n'a "
                      "rien dit")

    def test_supprimer_la_protection_reelle_est_attrape(self):
        d = self._dossier()
        self._muter(d, r'^\s*env\.pop\("ALPACA_LIVE_TRADE".*\)\n', "",
                    "retrait du env.pop dans cli_env")
        self.assertIn(self.MSG_FUITE, self._verdict(d),
                      "cli_env() laisse passer ALPACA_LIVE_TRADE au CLI et "
                      "garde_fou.py n'a rien dit")


GIT = shutil.which("git")


@unittest.skipUnless(GIT, "git absent — contrôles de dépôt sautés")
class TestGardeFouDitQuandIlEstAveugle(unittest.TestCase):
    """Le contrôle du fichier scellé s'appuie sur deux commandes git. Aucune
    des deux ne regardait son code de retour.

    Mesuré le 27/08 : hors d'un dépôt, `git ls-files` sort en 128 avec un
    stdout VIDE — soit exactement ce que rend un dépôt propre. Une commande qui
    ÉCHOUE était donc lue comme « aucun fichier suivi, tout va bien ».

    Et `git log --all --full-history` sur un clone superficiel ne voit qu'un
    commit (mesuré : 1 contre 66). Le workflow CI fixe fetch-depth: 0 pour
    cette raison, et son propre commentaire admet la limite — « testé une fois
    avant de pousser, jamais après ». Rien ne vérifiait que le réglage reste.

    Ni l'un ni l'autre ne BLOQUE : ne pas pouvoir vérifier n'est pas la preuve
    d'une fuite. Mais c'est dit, au lieu d'être compté comme un succès.
    """

    RACINE = Path(__file__).resolve().parent

    def _sortie_dans(self, dossier):
        shutil.copy(self.RACINE / "garde_fou.py", dossier / "garde_fou.py")
        proc = subprocess.run([sys.executable, "garde_fou.py"], cwd=str(dossier),
                              capture_output=True, text=True, timeout=120)
        return proc.stdout + proc.stderr

    def _git(self, dossier, *args):
        subprocess.run([GIT, *args], cwd=str(dossier), capture_output=True,
                       text=True, timeout=30, check=True)

    def test_hors_depot_le_controle_avoue_n_avoir_rien_prouve(self):
        d = Path(tempfile.mkdtemp(prefix="hindsight-horsgit-"))
        try:
            sortie = self._sortie_dans(d)
        finally:
            shutil.rmtree(d, ignore_errors=True)
        self.assertIn("ls-files` a echoue", sortie,
                      "git a échoué et le contrôle n'a rien dit : un stdout "
                      "vide était lu comme « aucun fichier suivi »")
        self.assertIn("n'a rien prouve", sortie)

    def test_un_clone_superficiel_est_signale_comme_aveugle(self):
        base = Path(tempfile.mkdtemp(prefix="hindsight-shallow-"))
        origine, clone = base / "origine", base / "clone"
        try:
            origine.mkdir()
            self._git(origine, "init", "-q")
            self._git(origine, "config", "user.email", "t@t")
            self._git(origine, "config", "user.name", "t")
            for i in range(2):
                (origine / ("f%d.txt" % i)).write_text("x", encoding="utf-8")
                self._git(origine, "add", "-A")
                self._git(origine, "commit", "-qm", "c%d" % i)
            subprocess.run([GIT, "clone", "--depth", "1", "-q",
                            "file://" + str(origine), str(clone)],
                           capture_output=True, text=True, timeout=60, check=True)
            profondeur = subprocess.run(
                [GIT, "rev-parse", "--is-shallow-repository"], cwd=str(clone),
                capture_output=True, text=True, timeout=30).stdout.strip()
            self.assertEqual(profondeur, "true",
                             "prérequis : le clone doit bien être superficiel")
            sortie = self._sortie_dans(clone)
        finally:
            shutil.rmtree(base, ignore_errors=True)
        self.assertIn("SUPERFICIEL", sortie,
                      "le contrôle d'historique est aveugle sur un clone "
                      "superficiel et ne le signale pas")

    def _est_un_depot_complet(self):
        """Ce dossier est-il un dépôt git non superficiel ?

        La question n'est pas rhétorique : ce test a d'abord été écrit en le
        SUPPOSANT, et il est tombé sur une reproduction de l'environnement CI
        obtenue par extraction d'archive — qui n'est pas un dépôt. Le vrai CI en
        est un (actions/checkout), donc il serait passé là-bas ; mais un test
        qui rougit selon la façon dont on a obtenu les fichiers n'apprend rien.
        On saute quand la prémisse n'est pas réunie, au lieu d'affirmer."""
        dedans = subprocess.run([GIT, "rev-parse", "--is-inside-work-tree"],
                                cwd=str(self.RACINE), capture_output=True,
                                text=True, timeout=30)
        if dedans.returncode != 0 or dedans.stdout.strip() != "true":
            return False
        superficiel = subprocess.run([GIT, "rev-parse", "--is-shallow-repository"],
                                     cwd=str(self.RACINE), capture_output=True,
                                     text=True, timeout=30)
        return superficiel.stdout.strip() == "false"

    def test_un_depot_complet_ne_declenche_aucun_de_ces_deux_avertissements(self):
        """Contrôle : sans lui, avertir TOUJOURS passerait les deux tests
        ci-dessus."""
        if not self._est_un_depot_complet():
            self.skipTest("ce dossier n'est pas un dépôt git complet — les deux "
                          "avertissements y sont attendus, pas anormaux")
        proc = subprocess.run([sys.executable, "garde_fou.py"],
                              cwd=str(self.RACINE), capture_output=True,
                              text=True, timeout=120)
        sortie = proc.stdout + proc.stderr
        self.assertNotIn("SUPERFICIEL", sortie)
        self.assertNotIn("ls-files` a echoue", sortie)


class TestCroisementDeLUnivers(unittest.TestCase):
    """Le contrôle 5 vérifie que les livrables nomment le MÊME univers que
    DEFAULT_UNIVERSE dans agent.py.

    Trouvé le 27/08 : il était gardé par `len(univers_actuel) == 4` et cherchait
    un motif à exactement quatre groupes. Mesuré en mutant DEFAULT_UNIVERSE :

        4 symboles (différents) -> le contrôle proteste
        3 symboles              -> SILENCE
        5 symboles              -> SILENCE

    Il ne fonctionnait donc que pour la taille d'univers du jour, et
    disparaissait au moment précis où il sert : quand l'univers change,
    c'est-à-dire quand les livrables deviennent faux.
    """

    RACINE = Path(__file__).resolve().parent
    # BACKTEST_RESULTS.md est indispensable : sans lui le contrôle 5 sort
    # immédiatement (« introuvable ou illisible — contrôle 5 sans effet ») et le
    # test ne vérifierait rien. Trouvé en écrivant ce test : les trois mutations
    # passaient sans être détectées, non pas parce que le contrôle est faible,
    # mais parce qu'il ne s'exécutait pas du tout.
    FICHIERS = ("garde_fou.py", "agent.py", "README.md",
                "BACKTEST_RESULTS.md", "STRATEGY_COMPARISON.md")

    def _dossier(self, univers=None):
        d = Path(tempfile.mkdtemp(prefix="hindsight-univers-"))
        for nom in self.FICHIERS:
            source = self.RACINE / nom
            if not source.exists():
                self.skipTest("%s absent — le contrôle 5 ne s'exécuterait pas" % nom)
            shutil.copy(source, d / nom)
        script = self.RACINE / "submission" / "Video_Script.md"
        if script.exists():
            (d / "submission").mkdir(exist_ok=True)
            shutil.copy(script, d / "submission" / "Video_Script.md")
        if univers is not None:
            chemin = d / "agent.py"
            avant = chemin.read_text(encoding="utf-8")
            apres = re.sub(r"^DEFAULT_UNIVERSE = \[[^\]]*\]",
                           "DEFAULT_UNIVERSE = [%s]" % ", ".join('"%s"' % t for t in univers),
                           avant, count=1, flags=re.M)
            self.assertNotEqual(avant, apres,
                                "la mutation de DEFAULT_UNIVERSE n'a rien changé : "
                                "agent.py a changé de forme et ce test ne vérifie plus rien")
            chemin.write_text(apres, encoding="utf-8")
        return d

    def _sortie(self, dossier):
        proc = subprocess.run([sys.executable, "garde_fou.py"], cwd=str(dossier),
                              capture_output=True, text=True, timeout=120)
        shutil.rmtree(dossier, ignore_errors=True)
        return proc.stdout + proc.stderr

    def _detecte(self, sortie):
        return "UNIVERS" in sortie or "mentionne nulle part" in sortie

    def test_un_univers_inchange_ne_declenche_rien(self):
        """Contrôle : c'est LUI qui a fait retirer la première version du
        correctif. Généraliser sans resserrer produisait trois faux positifs
        sur le dépôt sain — la prose mentionne légitimement des
        sous-ensembles (« SPY, GLD and XLV pass clean »). Un contrôle qui crie
        sur du texte correct est pire que celui qui se taisait."""
        self.assertFalse(self._detecte(self._sortie(self._dossier())),
                         "le dépôt sain déclenche le croisement d'univers")

    def test_un_univers_de_meme_taille_mais_different_est_detecte(self):
        self.assertTrue(self._detecte(self._sortie(
            self._dossier(["QQQ", "IWM", "TLT", "GLD"]))))

    def test_un_univers_plus_petit_est_detecte(self):
        self.assertTrue(self._detecte(self._sortie(
            self._dossier(["SPY", "GLD", "XLK"]))),
            "l'univers a rétréci et les livrables citent encore un symbole "
            "qui n'y est plus : le contrôle se taisait")

    def test_un_univers_plus_grand_est_detecte(self):
        self.assertTrue(self._detecte(self._sortie(
            self._dossier(["SPY", "GLD", "XLK", "XLV", "QQQ"]))),
            "l'univers a grandi et aucun livrable ne mentionne le nouveau "
            "symbole : le contrôle se taisait")


@unittest.skipUnless(GIT, "git absent")
class TestHooksBranches(unittest.TestCase):
    """CLAUDE.md décrit une protection en TROIS couches et dit d'activer la
    première « une fois par clone » : git config core.hooksPath githooks.

    Rien ne vérifiait que ce soit fait. Mesuré le 27/08 : dans un clone où
    hooksPath n'est pas configuré, on peut supprimer le refus paper-uniquement
    de config.py et COMMITTER — le hook n'existe pas, garde_fou.py n'est jamais
    lancé, et rien ne dit que la couche est absente. Vérifié des deux côtés :
    hooksPath configuré -> commit REFUSÉ ; hooksPath absent -> commit passe.
    """

    RACINE = Path(__file__).resolve().parent

    def _clone(self, hooks_path=None):
        d = Path(tempfile.mkdtemp(prefix="hindsight-hooks-"))
        shutil.copy(self.RACINE / "garde_fou.py", d / "garde_fou.py")
        shutil.copytree(self.RACINE / "githooks", d / "githooks")
        subprocess.run([GIT, "init", "-q", "."], cwd=str(d), check=True,
                       capture_output=True, timeout=30)
        if hooks_path is not None:
            subprocess.run([GIT, "config", "core.hooksPath", hooks_path],
                           cwd=str(d), check=True, capture_output=True, timeout=30)
        return d

    def _sortie(self, dossier, env_ci=False):
        env = dict(os.environ)
        env.pop("GITHUB_ACTIONS", None)
        env.pop("CI", None)
        if env_ci:
            env["GITHUB_ACTIONS"] = "true"
        proc = subprocess.run([sys.executable, "garde_fou.py"], cwd=str(dossier),
                              capture_output=True, text=True, timeout=120, env=env)
        shutil.rmtree(dossier, ignore_errors=True)
        return proc.stdout + proc.stderr

    def test_un_clone_non_configure_est_signale(self):
        sortie = self._sortie(self._clone())
        self.assertIn("core.hooksPath N'EST PAS CONFIGURE", sortie,
                      "la première couche de protection est absente et rien "
                      "ne le dit")
        self.assertIn("git config core.hooksPath githooks", sortie,
                      "l'alerte ne donne pas la commande qui corrige")

    def test_un_clone_configure_ne_declenche_rien(self):
        """Contrôle : sans lui, alerter TOUJOURS passerait le test du dessus."""
        self.assertNotIn("hooksPath", self._sortie(self._clone("githooks")))

    def test_un_hooksPath_qui_pointe_ailleurs_est_signale(self):
        sortie = self._sortie(self._clone(".git/hooks"))
        self.assertIn("pointe vers", sortie)

    def test_la_CI_ne_recoit_pas_cette_alerte(self):
        """Les hooks n'ont aucun sens en CI — aucun commit n'y est fait, et la
        CI EST la couche de protection à cet endroit. Alerter à chaque run
        apprendrait à ignorer les 🟡."""
        self.assertNotIn("hooksPath", self._sortie(self._clone(), env_ci=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
