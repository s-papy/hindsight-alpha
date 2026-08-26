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
import math
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


class TestGardePaperUniquement(unittest.TestCase):
    """La garantie la plus forte du projet : paper trading uniquement.

    Deux couches, et il faut les distinguer :

    1. `cli_env()` RETIRE `ALPACA_LIVE_TRADE` de l'environnement passé au CLI.
       C'est la protection réelle, et elle est absolue : le CLI ne peut pas
       voir une variable absente, quelle que soit sa graphie.
    2. `require_credentials()` refuse de démarrer sur une valeur non
       explicitement fausse. C'est le diagnostic.

    La couche 1 tenait déjà. La couche 2 avait des trous : la liste énumérait
    les valeurs VRAIES (`true`, `1`, `yes`), donc `on`, `y`, `t`, `2` et
    `enabled` passaient pour du paper. Pas un risque de trading réel — mais un
    opérateur qui croyait activer le live était silencieusement ignoré.
    Corrigé en énumérant les valeurs FAUSSES : tout le reste fait refuser.
    """

    def _demarre(self, valeur):
        """True si `require_credentials()` laisse démarrer avec cette valeur.

        Des identifiants FACTICES sont injectés, et ce n'est pas cosmétique :
        `require_credentials()` sort d'abord sur des clés manquantes, AVANT
        d'atteindre le contrôle paper. Sans eux, ce test mesurerait la présence
        d'un `.env` au lieu du comportement de la garde.

        Trouvé par la CI : ces tests passaient en local — où un `.env` existe —
        et échouaient sur GitHub, où il n'y en a pas. Un environnement propre
        est le seul juge honnête d'un test. `load_dotenv()` n'écrase pas une
        variable déjà présente, donc l'injection fait autorité dans les deux
        environnements."""
        import subprocess
        env = dict(os.environ)
        env["ALPACA_API_KEY"] = "cle-factice-pour-test"
        env["ALPACA_SECRET_KEY"] = "secret-factice-pour-test"
        if valeur is None:
            env.pop("ALPACA_LIVE_TRADE", None)
        else:
            env["ALPACA_LIVE_TRADE"] = valeur
        r = subprocess.run(
            [sys.executable, "-c", "import config; config.require_credentials(); print('OK')"],
            capture_output=True, text=True, env=env,
            cwd=os.path.dirname(os.path.abspath(__file__)), timeout=60,
        )
        return "OK" in r.stdout

    def test_les_valeurs_fausses_laissent_demarrer(self):
        for v in (None, "", "false", "FALSE", "0", "no", "off", "n", "f", "  False  "):
            with self.subTest(valeur=v):
                self.assertTrue(self._demarre(v),
                                "%r est une valeur fausse et devrait laisser démarrer" % v)

    def test_toute_graphie_vraie_fait_refuser(self):
        for v in ("true", "TRUE", " True ", "1", "yes", "YES", "on", "y", "t", "2"):
            with self.subTest(valeur=v):
                self.assertFalse(self._demarre(v),
                                 "%r demande le live et l'agent démarre quand même" % v)

    def test_une_valeur_ININTERPRETABLE_fait_refuser(self):
        """Une valeur qu'on ne sait pas lire n'est pas une permission de supposer."""
        for v in ("oui", "enabled", "maybe", "42x", "-"):
            with self.subTest(valeur=v):
                self.assertFalse(self._demarre(v),
                                 "%r est ininterprétable et l'agent démarre quand même" % v)

    def test_cli_env_retire_toujours_le_drapeau(self):
        """La protection RÉELLE : le CLI ne voit jamais la variable.

        Elle doit tenir même sur une graphie que la couche 1 ne reconnaîtrait
        pas — c'est précisément ce qui faisait que le trou de diagnostic
        n'était pas un trou de sécurité."""
        import config
        for v in ("true", "on", "y", "2", "enabled", "n'importe quoi"):
            with self.subTest(valeur=v):
                ancien = os.environ.get("ALPACA_LIVE_TRADE")
                os.environ["ALPACA_LIVE_TRADE"] = v
                try:
                    self.assertNotIn("ALPACA_LIVE_TRADE", config.cli_env(),
                                     "le drapeau atteint l'environnement du CLI")
                finally:
                    if ancien is None:
                        os.environ.pop("ALPACA_LIVE_TRADE", None)
                    else:
                        os.environ["ALPACA_LIVE_TRADE"] = ancien


class TestHindsightGuard(unittest.TestCase):
    """Le mécanisme central du projet : le test de fuite lui-même.

    Il tient en une quarantaine de lignes, et c'est là que ça compte — si ce
    verdict est faux, tout l'argument du projet tombe.

    LE DÉFAUT TROUVÉ, ET IL DÉPENDAIT DE L'ORDRE. `max()` compare avec `>`, et
    toute comparaison avec NaN rend False. Mesuré avant correctif :

        {"A": nan, "B": 1.0}  -> gagnant A, agrees=False  (échoue fermé)
        {"A": 1.0, "B": nan}  -> gagnant A, agrees=TRUE   (le NaN est écarté
                                  en silence, et le garde CERTIFIE l'absence
                                  de fuite)

    Un candidat qu'on n'a pas pu noter n'est pas un candidat qui a perdu. Si le
    vrai meilleur échoue à se noter sur une fenêtre, il disparaît sans bruit et
    un autre est déclaré propre.

    PORTÉE HONNÊTE : non atteignable aujourd'hui par `vol_strategy.py` — vérifié
    sur barres courtes, prix plats et un prix à zéro, tous donnent 0.0 fini.
    Mais cette bibliothèque est explicitement conçue pour un `score_fn`
    quelconque, donc le cas est ouvert pour tout autre appelant.
    """

    @staticmethod
    def _verdict(full, in_sample, seuil=0.0):
        from hindsight_guard import check_selection_leakage
        return check_selection_leakage(
            list(full), lambda c, w: (full if w == "full" else in_sample)[c],
            threshold=seuil)

    def test_un_score_non_fini_empeche_de_conclure_quelle_que_soit_sa_position(self):
        """Le cœur du défaut : le verdict ne doit pas dépendre de l'ordre."""
        nan = float("nan")
        for scores, position in (({"A": nan, "B": 1.0}, "premier"),
                                 ({"A": 1.0, "B": nan}, "second"),
                                 ({"A": 1.0, "B": float("inf")}, "infini")):
            with self.subTest(position=position):
                r = self._verdict(scores, dict(scores))
                self.assertFalse(r.agrees,
                                 "un score non fini en %s position laisse certifier "
                                 "l'absence de fuite" % position)
                self.assertTrue(r.unscorable, "le candidat fautif doit être nommé")
                self.assertIn("CANNOT CONCLUDE", r.summary())

    def test_le_cas_normal_nest_pas_affecte(self):
        """Contrepartie : un garde qui refuse tout ne sert à rien."""
        r = self._verdict({"A": 2.0, "B": 1.0}, {"A": 2.0, "B": 1.0})
        self.assertTrue(r.agrees)
        self.assertEqual(r.unscorable, [])

    def test_un_desaccord_reste_une_fuite(self):
        r = self._verdict({"A": 2.0, "B": 1.0}, {"B": 2.0, "A": 1.0})
        self.assertFalse(r.agrees)
        self.assertIn("LEAK DETECTED", r.summary())

    def test_rien_au_dessus_du_seuil_reste_un_refus(self):
        r = self._verdict({"A": 2.0, "B": 1.0}, {"A": -1.0, "B": -2.0})
        self.assertFalse(r.agrees)
        self.assertFalse(r.in_sample_clears_bar)

    def test_le_seuil_est_strict(self):
        """Pile au seuil ne passe pas : `>` et non `>=`."""
        self.assertFalse(self._verdict({"A": 9.0}, {"A": 0.0}).in_sample_clears_bar)
        self.assertTrue(self._verdict({"A": 9.0}, {"A": 1e-9}).in_sample_clears_bar)

    def test_aucun_candidat_donne_une_erreur_qui_explique(self):
        """`max() arg is an empty sequence` ne dit rien à l'appelant."""
        with self.assertRaises(ValueError) as ctx:
            self._verdict({}, {})
        self.assertIn("at least one candidate", str(ctx.exception))

    def test_la_vraie_fonction_de_score_ne_produit_jamais_de_non_fini(self):
        """Vérifie la portée annoncée plus haut plutôt que de l'affirmer.

        Barres absentes, trop courtes, prix strictement plats, et un prix à
        zéro — le cas qui pourrait diviser par zéro."""
        import vol_strategy
        from vol_strategy import Bar
        cas = {
            "aucune barre": [],
            "une barre": [Bar(close=100.0)],
            "prix plats": [Bar(close=100.0) for _ in range(300)],
            "un prix a zero": [Bar(close=100.0)] * 150 + [Bar(close=0.0)] + [Bar(close=100.0)] * 150,
        }
        for nom, barres in cas.items():
            for split in ("full", "in_sample"):
                with self.subTest(cas=nom, split=split):
                    score = vol_strategy.score_hv_window(10, split, barres)
                    self.assertTrue(math.isfinite(score),
                                    "score_hv_window rend un non-fini sur %r" % nom)


class TestPlafondsDeRisque(BaseExit):
    """Le dimensionnement : combien d'argent l'agent expose réellement.

    Vérifié à la main le 26/08 et trouvé CORRECT — aucun défaut. Ces tests
    existent parce que cette logique n'avait aucune couverture, alors que
    c'est elle qui décide du montant risqué. Un correctif futur sur les
    plafonds n'aurait rien eu pour le rattraper.

    Le plafond SECTEUR est un cas particulier : avec l'univers actuel il y a un
    seul symbole par secteur, donc le blocage par sous-jacent duplique le
    couvre toujours en premier — le README l'admet explicitement. Le test
    l'exerce en élargissant `SECTOR_MAP`, ce qui est exactement la situation
    que le README annonce (« stops being a no-op the moment the universe grows
    past one symbol per sector »). Sans ça, on ne saurait pas si ce contrôle
    marche, seulement qu'il n'est jamais atteint.
    """

    EQUITE = 100000.0

    def setUp(self):
        super().setUp()
        alpaca_cli.get_account = lambda: {
            "id": "compte-test", "equity": str(self.EQUITE),
            "portfolio_value": str(self.EQUITE)}
        alpaca_cli.get_option_ask_price = lambda s: 2.80
        self._secteurs = dict(risk_gates.SECTOR_MAP)

    def tearDown(self):
        risk_gates.SECTOR_MAP.clear()
        risk_gates.SECTOR_MAP.update(self._secteurs)
        super().tearDown()

    @staticmethod
    def _ouverte(symbole, cout):
        return {"symbol": symbole, "asset_class": "us_option",
                "cost_basis": str(cout), "unrealized_plpc": "0.0", "qty": "1"}

    def _decide(self, ouvertes=(), ask=2.80, sous_jacent="XLV",
                option="XLV260831C00150000"):
        self.positions = list(ouvertes)
        alpaca_cli.get_option_ask_price = lambda s: ask
        return risk_gates.check_gates(sous_jacent, option)

    @staticmethod
    def _autorise(d):
        return bool(getattr(d, "allowed", getattr(d, "ok", False)))

    def test_le_cout_est_par_CONTRAT_de_cent_actions(self):
        """Une option se cote par action, se vend par contrat de 100.

        Sans le facteur 100, un ask de 12 $ compterait pour 12 $ au lieu de
        1200 $ — et l'agent achèterait environ 83 fois trop."""
        d = self._decide(ask=12.00)   # 1200 $ le contrat, plafond par trade 1000 $
        self.assertFalse(self._autorise(d),
                         "un contrat à 1200 $ passe sous un plafond de 1000 $ — "
                         "le facteur 100 a disparu")
        self.assertIn("1,200", str(getattr(d, "reason", "")))

    def test_le_plafond_par_trade_dimensionne_a_la_baisse(self):
        d = self._decide(ask=2.80)    # 280 $ le contrat, 1000 $ disponibles
        self.assertTrue(self._autorise(d))
        self.assertIn("3 contract", str(getattr(d, "reason", "")),
                      "3 × 280 = 840 $ tient sous 1000 $, 4 n'y tiendrait pas")

    def test_les_positions_deja_ouvertes_reduisent_le_budget_restant(self):
        """Le point que le README met en avant : une 2e position ne repart pas
        avec un 1 % tout neuf, elle puise dans le 3 % commun."""
        d = self._decide([self._ouverte("SPY260831P00500000", 2500)])
        self.assertTrue(self._autorise(d))
        self.assertIn("1 contract", str(getattr(d, "reason", "")),
                      "500 $ restants sous le plafond total : un seul contrat")

        d = self._decide([self._ouverte("SPY260831P00500000", 2900)])
        self.assertFalse(self._autorise(d), "100 $ restants, un contrat en coûte 280")

        d = self._decide([self._ouverte("SPY260831P00500000", 3000)])
        self.assertFalse(self._autorise(d))
        self.assertIn("total exposure cap", str(getattr(d, "reason", "")))

    def test_le_plafond_par_secteur_somme_plusieurs_symboles(self):
        risk_gates.SECTOR_MAP["VHT"] = "healthcare"
        risk_gates.SECTOR_MAP["IHI"] = "healthcare"

        d = self._decide([self._ouverte("VHT260831C00250000", 1000)])
        self.assertTrue(self._autorise(d))
        self.assertIn("1 contract", str(getattr(d, "reason", "")))

        d = self._decide([self._ouverte("VHT260831C00250000", 1500)])
        self.assertFalse(self._autorise(d))
        self.assertIn("sector concentration cap", str(getattr(d, "reason", "")))

        # deux symboles du MÊME secteur doivent s'additionner
        d = self._decide([self._ouverte("VHT260831C00250000", 800),
                          self._ouverte("IHI260831C00050000", 800)])
        self.assertFalse(self._autorise(d),
                         "800 + 800 dans le même secteur dépasse 1500 et devrait bloquer")

    def test_un_autre_secteur_ne_consomme_pas_le_budget_sante(self):
        """Contre-épreuve : un plafond qui bloquerait tout ne prouverait rien."""
        d = self._decide([self._ouverte("XLK260831C00200000", 1500)])
        self.assertTrue(self._autorise(d),
                        "1500 $ en technologie bloquent une entrée en santé — "
                        "les secteurs ne sont pas séparés")

    def test_jamais_deux_positions_sur_le_meme_sous_jacent(self):
        d = self._decide([self._ouverte("XLV260831P00140000", 500)])
        self.assertFalse(self._autorise(d))
        self.assertIn("already holding", str(getattr(d, "reason", "")))

    def test_le_plafond_de_positions_simultanees(self):
        ouvertes = [self._ouverte(s, 200) for s in
                    ("SPY260831C00500000", "GLD260831C00200000",
                     "XLK260831C00200000", "IWM260831C00200000")]
        d = self._decide(ouvertes)
        self.assertFalse(self._autorise(d))
        self.assertIn("concurrent-position cap", str(getattr(d, "reason", "")))


class TestInvariantDAlignement(unittest.TestCase):
    """L'invariant que `_hv_series` déclare « load-bearing » — et que rien
    n'empêchait de casser.

    LE RISQUE, écrit par le fichier lui-même : « a future edit that makes
    range(window, len(returns)+1) -- so hv[-1] finally uses the last return --
    would silently break the correspondence on ONE side only, and the numbers
    would still look plausible. »

    C'est la définition d'un défaut qu'aucune relecture n'attrape : les
    résultats restent crédibles, seul le backtest devient plus favorable que la
    règle réellement tradée. Dans un projet nommé d'après la fuite par
    anticipation, ce serait le pire endroit où en laisser une.

    Le docstring dit avoir vérifié numériquement le 24/08. Re-vérifié le 26/08
    — l'invariant tient — et transformé en test, parce qu'une vérification
    ponctuelle protège le jour où elle est faite, pas les suivants.

    LA MÉTHODE compte : on ne réaffirme pas la formule (un test qui recopie la
    formule du code passe même quand les deux sont faux ensemble). On
    PERTURBE une donnée d'entrée et on observe laquelle change le résultat.
    """

    FENETRE = 5

    def _series(self):
        from vol_strategy import Bar
        import vol_strategy
        bars = [Bar(close=100.0 * (1.01 ** i)) for i in range(40)]
        return vol_strategy, vol_strategy.daily_returns(bars)

    def test_hv_k_ne_voit_pas_le_rendement_du_jour_meme(self):
        """hv[k] doit s'arrêter à rets[W+k-1]. S'il voyait rets[W+k], la
        volatilité utilisée pour décider inclurait le mouvement qu'elle est
        censée précéder."""
        vs, rets = self._series()
        W = self.FENETRE
        hv = vs._hv_series(rets, W)

        for k in (0, 1, len(hv) - 1):
            with self.subTest(k=k):
                dernier_attendu = W + k - 1

                def hv_perturbe(indice):
                    r = list(rets)
                    r[indice] += 0.5
                    return vs._hv_series(r, W)[k]

                self.assertNotAlmostEqual(
                    hv_perturbe(dernier_attendu), hv[k],
                    msg="hv[%d] ignore rets[%d], qu'il devrait utiliser" % (k, dernier_attendu))
                if dernier_attendu + 1 < len(rets):
                    self.assertAlmostEqual(
                        hv_perturbe(dernier_attendu + 1), hv[k],
                        msg="hv[%d] utilise rets[%d] — il voit un jour de TROP, "
                            "c'est-à-dire le futur" % (k, dernier_attendu + 1))

    def test_le_decalage_decision_gain_est_le_meme_en_backtest_et_en_live(self):
        """Le cœur de l'invariant : si les deux écarts diffèrent, le backtest
        mesure une règle plus favorable que celle réellement tradée."""
        vs, rets = self._series()
        W = self.FENETRE
        hv = vs._hv_series(rets, W)

        # Backtest : décide sur hv[i], encaisse rets[W+i+1] (cf.
        # _vol_strategy_returns, `next_day_ret_index = window + i + 1`).
        i = 10
        ecart_backtest = (W + i + 1) - (W + i - 1)

        # Live : décide sur hv[-1], achète maintenant, capte le mouvement de
        # DEMAIN — soit rets[len(rets)], pas encore observé.
        k = len(hv) - 1
        ecart_live = len(rets) - (W + k - 1)

        self.assertEqual(
            ecart_backtest, ecart_live,
            "le backtest saute %d jour(s) entre décision et gain, le live %d : "
            "les deux ne mesurent pas la même règle" % (ecart_backtest, ecart_live))
        self.assertEqual(ecart_backtest, 2,
                         "l'écart attendu est 2 (un jour entier ignoré entre les deux)")

    def test_la_distribution_de_reference_exclut_l_observation_courante(self):
        """Un percentile qui s'inclut lui-même est biaisé — et il le serait
        différemment des deux côtés si un seul chemin le faisait."""
        import inspect
        import vol_strategy
        backtest = inspect.getsource(vol_strategy._vol_strategy_returns)
        live = inspect.getsource(vol_strategy.today_regime)
        self.assertIn("hv[max(0, i - RANK_LOOKBACK_DAYS):i]", backtest,
                      "le backtest n'exclut plus hv[i] de sa propre distribution")
        self.assertIn(":-1]", live,
                      "le chemin live n'exclut plus hv[-1] de sa propre distribution")


class TestFrontiereCLI(unittest.TestCase):
    """La frontière avec l'extérieur : ce que `run()` accepte comme réponse.

    DEUX REPLIS SILENCIEUX, tous deux du côté dangereux, tous deux dans le
    seul mécanisme qui protège une position ouverte.

    1. `run()` ne jugeait que le CODE DE SORTIE. Or le CLI a une forme
       d'erreur dans sa sortie elle-même — `{"code": 0, "error": "could not
       reach ..."}`, vue telle quelle dans decision_log.jsonl. Rien ne
       garantit que ce corps arrive toujours avec un code non nul.

       Tracé bout en bout : `get_clock()` rendrait le dict d'erreur,
       `.get("is_open", False)` vaudrait False, le moniteur conclurait
       « market closed », journaliserait `market_closed` et NON `error`, et la
       bannière afficherait **🟢 healthy**. Une API injoignable devenue un
       marché fermé, avec la page au vert.

    2. `list_positions()` finissait par `return data if isinstance(data, list)
       else []`. Toute réponse incomprise devenait « aucune position ouverte »
       — donc `manage_exits()` ne vérifiait AUCUN stop-loss, sans une ligne de
       journal pour le dire.

    PORTÉE HONNÊTE : le cas d'erreur observé sortait en code 1, donc était déjà
    attrapé. Ces tests ferment des chemins LATENTS. Ils sont là parce que le
    coût d'avoir tort est exactement le mode de panne que ce projet existe pour
    empêcher.
    """

    def setUp(self):
        # Sauvegarder TOUT ce que ces tests remplacent. La premiere version ne
        # gardait que `run`, et le dernier test laissait un `list_positions`
        # piege en place: quatre tests suivants echouaient sur un etat pollue
        # par un autre. L'ironie est notee -- une suite qui epingle des defauts
        # d'isolation en avait un.
        self._sauve = {nom: getattr(alpaca_cli, nom)
                       for nom in ("run", "list_positions")}

    def tearDown(self):
        for nom, valeur in self._sauve.items():
            setattr(alpaca_cli, nom, valeur)

    def test_une_charge_derreur_leve_meme_avec_un_code_de_sortie_nul(self):
        import json as _json
        import types
        vrais = (alpaca_cli._require_binary, alpaca_cli._check_cli_version,
                 alpaca_cli.subprocess)
        import config
        vrai_creds = config.require_credentials

        class Resultat:
            returncode, stderr = 0, ""
            stdout = _json.dumps({"code": 0, "error": "could not reach https://..."})

        alpaca_cli._require_binary = lambda: None
        alpaca_cli._check_cli_version = lambda: None
        config.require_credentials = lambda: None
        alpaca_cli.subprocess = types.SimpleNamespace(
            run=lambda *a, **k: Resultat(), TimeoutExpired=Exception)
        try:
            with self.assertRaises(alpaca_cli.AlpacaCLIError) as ctx:
                alpaca_cli.run(["clock"])
            self.assertIn("error payload", str(ctx.exception))
        finally:
            (alpaca_cli._require_binary, alpaca_cli._check_cli_version,
             alpaca_cli.subprocess) = vrais
            config.require_credentials = vrai_creds

    def test_une_cle_error_vide_reste_une_reponse_valide(self):
        """Contre-épreuve : `error: null` ne doit pas faire échouer un appel
        parfaitement normal."""
        import json as _json
        import types
        vrais = (alpaca_cli._require_binary, alpaca_cli._check_cli_version,
                 alpaca_cli.subprocess)
        import config
        vrai_creds = config.require_credentials

        for valeur in (None, ""):
            class Resultat:
                returncode, stderr = 0, ""
                stdout = _json.dumps({"id": "abc", "error": valeur})

            alpaca_cli._require_binary = lambda: None
            alpaca_cli._check_cli_version = lambda: None
            config.require_credentials = lambda: None
            alpaca_cli.subprocess = types.SimpleNamespace(
                run=lambda *a, **k: Resultat(), TimeoutExpired=Exception)
            try:
                with self.subTest(valeur=valeur):
                    self.assertEqual(alpaca_cli.run(["account", "get"])["id"], "abc")
            finally:
                (alpaca_cli._require_binary, alpaca_cli._check_cli_version,
                 alpaca_cli.subprocess) = vrais
                config.require_credentials = vrai_creds

    def test_un_vrai_vide_reste_un_vide(self):
        """Le correctif ne doit pas transformer une absence légitime de
        position en erreur."""
        for charge in (None, [], {"positions": []}, {}):
            with self.subTest(charge=charge):
                alpaca_cli.run = lambda a, _c=charge: _c
                self.assertEqual(alpaca_cli.list_positions(), [])

    def test_une_reponse_incomprise_ne_devient_pas_aucune_position(self):
        """Le cœur du défaut : « je n'ai pas compris » n'est pas « il n'y a
        rien ». Rendre [] ici ferait sauter TOUS les stop-loss en silence."""
        for charge in ({"code": 0, "data": "?"}, "une chaîne", 42):
            with self.subTest(charge=charge):
                alpaca_cli.run = lambda a, _c=charge: _c
                with self.assertRaises(alpaca_cli.AlpacaCLIError):
                    alpaca_cli.list_positions()

    def test_lexception_remonte_jusqu_a_manage_exits(self):
        """Elle doit atteindre monitor_exits, qui la journalise en `error` et
        fait passer la bannière au rouge — visible, pas silencieux."""
        def leve():
            raise alpaca_cli.AlpacaCLIError("réponse illisible")
        alpaca_cli.list_positions = leve
        # tearDown restaure -- pas de finally bricole ici.
        with self.assertRaises(alpaca_cli.AlpacaCLIError):
            risk_gates.manage_exits(dry_run=False)
