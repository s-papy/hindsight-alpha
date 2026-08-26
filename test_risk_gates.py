"""Regression tests for the exit and circuit-breaker chain.

Run: `python3 -m unittest test_risk_gates -v`   (standard library only)

WHY THIS FILE EXISTS
====================
`manage_exits()` and the consecutive-loss breaker are the only mechanisms
protecting an open position: Alpaca does not support bracket/OCO orders on
options, confirmed against the real API. There is no server-side stop. If this
chain is wrong, a losing position stays open with nothing watching it.

Every test here mocks the CLI layer — no network, no credentials, no order ever
submitted — and redirects `STATE_FILE` to a temporary directory, so running the
suite can never touch the real `state.json` or a real account.

`alpaca_cli.run()` — the single point through which this module reaches the CLI,
and therefore the network — is replaced by a raise. Any path left unstubbed
fails loudly here instead of quietly hitting a real account. That net is not
theoretical: the first version of this file stubbed `get_option_quote` while the
code calls `get_option_ask_price`, so on a machine with the CLI installed the
call went out for real and the test passed for the wrong reason. CI, having no
CLI, went red and exposed it.

WHAT EACH TEST PINS, AND WHY IT WOULD MATTER
--------------------------------------------
- **Units.** `unrealized_plpc` is a *fraction* (-0.42 = -42%), the thresholds
  are fractions too. If either side drifted to whole percent, the stop-loss
  would either never fire or fire on every position. The log line prints
  percent, which is exactly the kind of mismatch that hides in plain sight.
- **Boundary.** A position at exactly the threshold must close; one a hair
  short must not.
- **Counter.** A loss increments the streak, a win resets it. A counter that
  silently fails to increment turns the breaker into decoration.
- **Breaker.** At `MAX_CONSECUTIVE_LOSSES`, new entries must be refused.
- **Per-position isolation.** If closing position A raises, position B —
  checked later in the same loop — must still get its own check. The docstring
  in `manage_exits` calls this the one gap that fails on the *dangerous* side,
  and notes it was never triggered for real. This test triggers it.
- **Unreadable P&L.** A position whose P&L can't be parsed must be *reported*,
  never silently treated as "fine, holding".
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import alpaca_cli  # noqa: E402
import risk_gates  # noqa: E402


def position(symbol: str = "SPY260831P00764000", plpc: str = "-0.10") -> dict:
    """A position as the CLI actually returns it: every numeric field a string."""
    return {
        "symbol": symbol,
        "asset_class": "us_option",
        "unrealized_plpc": plpc,
        "unrealized_pl": "-100.0",
        "cost_basis": "938.0",
        "qty": "2",
    }


class BaseExit(unittest.TestCase):
    """Isolates state.json and stubs every call that would touch the network."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="hindsight-test-"))
        self._vrai_state = risk_gates.STATE_FILE
        risk_gates.STATE_FILE = self.tmp / "state.json"

        # `run()` est le SEUL point par lequel ce module atteint le CLI, donc
        # le reseau. On le remplace par une explosion : tout chemin qu'on aurait
        # oublie de boucher echoue bruyamment ICI, au lieu de partir sur le vrai
        # compte.
        #
        # Ce filet n'est pas theorique. Sa premiere version bouchait
        # `get_option_quote`, alors que le code appelle `get_option_ask_price`.
        # Sur une machine ou le CLI `alpaca` est installe, l'appel partait donc
        # POUR DE VRAI et le test passait pour la mauvaise raison ; la CI, sans
        # CLI, a rougi et revele la fuite. Boucher fonction par fonction ne
        # suffit pas -- il faut fermer la porte, pas les fenetres une a une.
        self._vrais = {
            nom: getattr(alpaca_cli, nom, None)
            for nom in ("run", "list_positions", "close_position", "get_account",
                        "get_clock", "get_option_ask_price")
        }

        def _interdit(*a, **k):
            raise AssertionError(
                "un test a tente d'atteindre le CLI Alpaca (donc le reseau) : "
                "args=%r. Bouche la fonction concernee dans setUp." % (a,))

        alpaca_cli.run = _interdit
        self.closed: list[str] = []
        alpaca_cli.list_positions = lambda: list(self.positions)
        alpaca_cli.close_position = self._close
        alpaca_cli.get_account = lambda: {
            "id": "compte-test", "equity": "100000.0", "portfolio_value": "100000.0"}
        alpaca_cli.get_clock = lambda: {"is_open": True}
        alpaca_cli.get_option_ask_price = lambda s: 4.69
        self.positions: list[dict] = []
        self.close_leve_sur: set[str] = set()

    def _close(self, symbol: str):
        if symbol in self.close_leve_sur:
            raise alpaca_cli.AlpacaCLIError("échec simulé de fermeture pour %s" % symbol)
        self.closed.append(symbol)
        return {"status": "ok"}

    def tearDown(self) -> None:
        for nom, valeur in self._vrais.items():
            if valeur is not None:
                setattr(alpaca_cli, nom, valeur)
        risk_gates.STATE_FILE = self._vrai_state
        shutil.rmtree(self.tmp, ignore_errors=True)

    def etat(self) -> dict:
        if not risk_gates.STATE_FILE.exists():
            return {}
        return json.loads(risk_gates.STATE_FILE.read_text(encoding="utf-8"))


class TestSeuils(BaseExit):
    def test_les_seuils_sont_des_fractions_pas_des_pourcents(self):
        """-0.42 est -42%, bien au-dessus du stop à -0.50 : rien ne doit fermer.

        Si un côté passait en pourcent entier, -42 serait comparé à -0.50 et
        TOUTE position se fermerait immédiatement."""
        self.positions = [position(plpc="-0.42")]
        risk_gates.manage_exits(dry_run=False)
        self.assertEqual(self.closed, [], "une position à -42% a été fermée alors "
                                          "que le seuil est -50%")

    def test_le_stop_loss_ferme_au_dela_du_seuil(self):
        self.positions = [position(plpc="-0.55")]
        actions = risk_gates.manage_exits(dry_run=False)
        self.assertEqual(self.closed, ["SPY260831P00764000"])
        self.assertIn("stop-loss", str(actions[0]))

    def test_le_stop_loss_ferme_exactement_au_seuil(self):
        """Frontière : `<=` et non `<`. Une position pile au seuil doit fermer."""
        self.positions = [position(plpc="-%s" % risk_gates.STOP_LOSS_PCT)]
        risk_gates.manage_exits(dry_run=False)
        self.assertEqual(self.closed, ["SPY260831P00764000"])

    def test_le_take_profit_ferme_au_dela_du_seuil(self):
        self.positions = [position(plpc="0.55")]
        actions = risk_gates.manage_exits(dry_run=False)
        self.assertEqual(self.closed, ["SPY260831P00764000"])
        self.assertIn("take-profit", str(actions[0]))

    def test_dry_run_ne_ferme_jamais_rien(self):
        self.positions = [position(plpc="-0.99")]
        risk_gates.manage_exits(dry_run=True)
        self.assertEqual(self.closed, [], "dry_run a soumis un vrai ordre de fermeture")


class TestCompteurDePertes(BaseExit):
    def test_chaque_perte_incremente_le_compteur(self):
        self.positions = [position(plpc="-0.55")]
        for attendu in (1, 2, 3):
            risk_gates.manage_exits(dry_run=False)
            self.assertEqual(self.etat().get("consecutive_losses"), attendu)

    def test_une_victoire_remet_le_compteur_a_zero(self):
        self.positions = [position(plpc="-0.55")]
        risk_gates.manage_exits(dry_run=False)
        risk_gates.manage_exits(dry_run=False)
        self.assertEqual(self.etat().get("consecutive_losses"), 2)

        self.positions = [position(plpc="0.60")]
        risk_gates.manage_exits(dry_run=False)
        self.assertFalse(self.etat().get("consecutive_losses"),
                         "une prise de bénéfice n'a pas remis la série à zéro")

    def test_dry_run_ne_compte_pas_une_perte_simulee(self):
        """Une fermeture simulée n'est pas un vrai résultat à comptabiliser."""
        self.positions = [position(plpc="-0.55")]
        risk_gates.manage_exits(dry_run=True)
        self.assertFalse(self.etat().get("consecutive_losses"))


class TestDisjoncteur(BaseExit):
    def _decision(self):
        return risk_gates.check_gates("SPY", "SPY260831P00764000")

    @staticmethod
    def _autorise(decision) -> bool:
        return bool(getattr(decision, "allowed", getattr(decision, "ok", False)))

    def test_une_entree_passe_quand_la_serie_est_vide(self):
        self.assertTrue(self._autorise(self._decision()),
                        "aucune perte en série et pourtant l'entrée est refusée")

    def test_le_disjoncteur_bloque_au_maximum(self):
        # `starting_equity` est indispensable ici, et ce n'est pas cosmétique.
        # `_reconcile_state()` traite tout état dépourvu de cette clé — ou
        # rattaché à un AUTRE compte — comme non fiable, et le remet à plat,
        # compteur de pertes compris. C'est voulu : une série de pertes du
        # compte A ne doit jamais déclencher le disjoncteur du compte B.
        #
        # Première version de ce test : « week_start_equity ». Le test échouait
        # en annonçant « l'agent continue d'entrer après 3 pertes » — un faux
        # positif alarmant sur le mécanisme de sécurité. Le défaut était dans le
        # test, pas dans le code, et le code avait raison.
        risk_gates.STATE_FILE.write_text(json.dumps({
            "consecutive_losses": risk_gates.MAX_CONSECUTIVE_LOSSES,
            "account_id": "compte-test",
            "starting_equity": 100000.0,
        }), encoding="utf-8")
        decision = self._decision()
        self.assertFalse(self._autorise(decision),
                         "l'agent continue d'entrer après %d pertes consécutives"
                         % risk_gates.MAX_CONSECUTIVE_LOSSES)
        self.assertIn("consecutive", str(getattr(decision, "reason", "")).lower())


class TestIsolationParPosition(BaseExit):
    def test_un_echec_sur_A_ne_prive_pas_B_de_son_controle(self):
        """Le seul défaut de cette fonction qui échoue du côté DANGEREUX.

        Sans isolation, une exception en fermant A remonterait hors de la
        boucle, et B — pourtant lui aussi au-delà du stop — resterait ouvert,
        non géré, à cause d'un problème qui ne le concerne pas.

        Le docstring de `manage_exits` note que ce cas n'avait jamais été
        déclenché pour de vrai. Ce test le déclenche."""
        self.positions = [position("AAA260831P00100000", "-0.55"),
                          position("BBB260831P00100000", "-0.55")]
        self.close_leve_sur = {"AAA260831P00100000"}

        actions = risk_gates.manage_exits(dry_run=False)

        self.assertIn("BBB260831P00100000", self.closed,
                      "la seconde position n'a pas été fermée parce que la "
                      "première a échoué")
        self.assertEqual(len(actions), 2, "une action par position était attendue")
        self.assertIn("AAA260831P00100000", str(actions[0]))


class TestPnLIllisible(BaseExit):
    def test_un_pnl_illisible_est_signale_jamais_avale(self):
        """« Je n'ai pas pu lire » n'est pas « tout va bien ».

        Une position dont le P&L est inexploitable ne doit pas être rangée
        silencieusement avec les positions saines : sans signalement, elle
        resterait ouverte sans que personne ne sache qu'elle n'est pas suivie."""
        pos = position()
        pos["unrealized_plpc"] = "indisponible"
        pos.pop("unrealized_pl")
        pos.pop("cost_basis")
        self.positions = [pos]

        actions = risk_gates.manage_exits(dry_run=False)

        self.assertEqual(self.closed, [])
        self.assertEqual(len(actions), 1)
        self.assertIn("unreadable", str(actions[0]).lower() + str(getattr(actions[0], "kind", "")).lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
