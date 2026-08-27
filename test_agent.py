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


if __name__ == "__main__":
    unittest.main(verbosity=2)
