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


if __name__ == "__main__":
    unittest.main(verbosity=2)
