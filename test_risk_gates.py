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
import threading
import time
import unittest
from datetime import datetime, timezone
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
    """CES DEUX PREMIERS TESTS VERROUILLAIENT LE BUG jusqu'au 27/08.

    Ils fermaient LA MÊME position plusieurs fois de suite et attendaient
    1, 2, 3 — c'est-à-dire exactement le défaut corrigé ce jour-là : le
    compteur comptait des TENTATIVES DE FERMETURE, pas des positions fermées.
    Trois pertes consécutives, ce sont trois positions, pas une refermée trois
    fois. Corrigés pour dire ce qu'ils prétendaient vérifier.

    Deuxième fois de la nuit qu'un test consciencieux verrouillait le
    comportement fautif (voir aussi
    test_la_vraie_fonction_de_score_AVOUE_quand_elle_ne_peut_pas_mesurer)."""

    CONTRATS = ("SPY260831P00764000", "QQQ260831P00400000", "IWM260831P00200000")

    def test_chaque_perte_incremente_le_compteur(self):
        for i, attendu in enumerate((1, 2, 3)):
            self.positions = [position(symbol=self.CONTRATS[i], plpc="-0.55")]
            risk_gates.manage_exits(dry_run=False)
            self.assertEqual(self.etat().get("consecutive_losses"), attendu)

    def test_une_victoire_remet_le_compteur_a_zero(self):
        for i in (0, 1):
            self.positions = [position(symbol=self.CONTRATS[i], plpc="-0.55")]
            risk_gates.manage_exits(dry_run=False)
        self.assertEqual(self.etat().get("consecutive_losses"), 2)

        self.positions = [position(symbol=self.CONTRATS[2], plpc="0.60")]
        risk_gates.manage_exits(dry_run=False)
        self.assertFalse(self.etat().get("consecutive_losses"),
                         "une prise de bénéfice n'a pas remis la série à zéro")

    def test_une_position_bloquee_n_est_comptee_qu_une_fois(self):
        """close_position() soumet un ordre ; l'exécution est asynchrone. Entre
        la soumission et le fill, la position figure toujours dans
        list_positions(). Mesuré avant correctif : cinq passages sur la MÊME
        position donnaient consecutive_losses=5, donc MAX_CONSECUTIVE_LOSSES
        (3) atteint en 45 minutes au rythme de 15 min du moniteur — sur la foi
        de trois pertes qui n'en étaient qu'une."""
        self.positions = [position(symbol=self.CONTRATS[0], plpc="-0.55")]
        for _ in range(5):
            risk_gates.manage_exits(dry_run=False)
        self.assertEqual(self.etat().get("consecutive_losses"), 1,
                         "une seule position bloquée a été comptée plusieurs "
                         "fois : le disjoncteur saute sur des pertes fictives")

    def test_la_fermeture_est_bien_RE_TENTEE_a_chaque_passage(self):
        """Contrôle indispensable : ne plus recompter ne doit pas devenir ne
        plus refermer. La première tentative n'a pas pris effet — la position
        est toujours ouverte et toujours sous le seuil, il FAUT réessayer."""
        self.positions = [position(symbol=self.CONTRATS[0], plpc="-0.55")]
        for _ in range(3):
            risk_gates.manage_exits(dry_run=False)
        self.assertEqual(len(self.closed), 3,
                         "la position bloquée n'est plus re-fermée : le "
                         "correctif d'idempotence a désarmé la sortie")

    def test_une_vraie_seconde_perte_compte_toujours(self):
        """Contrôle : sans lui, « ne jamais rien compter deux fois » pourrait
        devenir « ne plus jamais compter »."""
        self.positions = [position(symbol=self.CONTRATS[0], plpc="-0.55")]
        risk_gates.manage_exits(dry_run=False)
        risk_gates.manage_exits(dry_run=False)
        self.positions = [position(symbol=self.CONTRATS[1], plpc="-0.55")]
        risk_gates.manage_exits(dry_run=False)
        self.assertEqual(self.etat().get("consecutive_losses"), 2)

    def test_une_issue_qui_change_est_recomptee(self):
        """La mémoire retient le couple (contrat, ISSUE). Avec le seul contrat,
        une position bloquée dont l'issue passe de perte à gain verrait son
        gain ignoré — donc le compteur ne serait pas remis à zéro, alors qu'un
        gain est précisément ce qui doit le remettre à zéro."""
        self.positions = [position(symbol=self.CONTRATS[0], plpc="-0.55")]
        risk_gates.manage_exits(dry_run=False)
        risk_gates.manage_exits(dry_run=False)
        self.assertEqual(self.etat().get("consecutive_losses"), 1)
        self.positions = [position(symbol=self.CONTRATS[0], plpc="0.60")]
        risk_gates.manage_exits(dry_run=False)
        self.assertFalse(self.etat().get("consecutive_losses"))

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

    def test_aucun_edge_nulle_part_n_est_pas_une_fuite(self):
        """Ajouté le 27/08, trouvé en faisant tourner le pipeline complet sur
        des barres synthétiques plausibles.

        Quand AUCUN candidat ne franchit le seuil — ni en in-sample, ni sur la
        fenêtre pleine — le résumé annonçait quand même :

            LEAK DETECTED: this selection depends on data outside the
              in-sample window.
              full-window winner: 90  (score -0.3807)
              -> the apparent winner exists only because the scoring window
                 included data that would not have been knowable at decision
                 time.

        Le gagnant « apparent » a un score NÉGATIF. Il n'existe pas « à cause
        de » données futures : il perd des deux côtés. Il n'y a pas de fuite,
        il n'y a pas d'edge. Annoncer une fuite là où rien n'a fuité est un
        faux positif dans le TITRE du module phare.

        Le refus reste entier — on ne trade pas. Seule la RAISON change, et
        c'est elle qu'un juge lit."""
        r = self._verdict({"A": -0.4, "B": -1.0}, {"A": -0.5, "B": -1.2})
        self.assertFalse(r.agrees, "prérequis : on refuse toujours de trader")
        texte = r.summary()
        self.assertNotIn("LEAK DETECTED", texte,
                         "fuite annoncée alors que rien ne gagne nulle part :\n%s"
                         % texte)
        self.assertNotIn("only because", texte,
                         "le résumé affirme une causalité fausse :\n%s" % texte)
        self.assertIn("NO EDGE", texte)

    def test_un_edge_qui_disparait_en_in_sample_reste_une_fuite(self):
        """Témoin indispensable, et c'est LE cas que le module existe pour
        attraper : la fenêtre pleine trouve quelque chose, l'in-sample non.
        Là, le gagnant existe bel et bien à cause de données non
        connaissables."""
        r = self._verdict({"A": 2.0, "B": 1.0}, {"A": -0.5, "B": -1.2})
        self.assertFalse(r.agrees)
        texte = r.summary()
        self.assertIn("LEAK DETECTED", texte)
        self.assertIn("only because", texte)

    def test_le_seuil_du_plein_est_strict_lui_aussi(self):
        """Pile AU seuil ne franchit pas, sur la fenêtre pleine comme en
        in-sample. Ajouté après qu'une mutation `>` -> `>=` soit restée verte :
        mes scores étaient à -0.4 contre un seuil de 0.0, donc la frontière
        n'était jamais touchée. Un test qui ne va pas au bord ne teste pas le
        bord."""
        from hindsight_guard import check_selection_leakage
        r = check_selection_leakage(
            ["A", "B"],
            lambda c, w: ({"A": 0.0, "B": -1.0}[c] if w == "full"
                          else {"A": -0.5, "B": -1.2}[c]),
            threshold=0.0)
        self.assertFalse(r._plein_franchit_le_seuil(),
                         "un score PILE au seuil est compté comme le "
                         "franchissant")
        self.assertIn("NO EDGE", r.summary(),
                      "pile au seuil des deux côtés doit rester « pas d'edge »")

    def test_le_seuil_est_strict(self):
        """Pile au seuil ne passe pas : `>` et non `>=`."""
        self.assertFalse(self._verdict({"A": 9.0}, {"A": 0.0}).in_sample_clears_bar)
        self.assertTrue(self._verdict({"A": 9.0}, {"A": 1e-9}).in_sample_clears_bar)

    def test_aucun_candidat_donne_une_erreur_qui_explique(self):
        """`max() arg is an empty sequence` ne dit rien à l'appelant."""
        with self.assertRaises(ValueError) as ctx:
            self._verdict({}, {})
        self.assertIn("at least one candidate", str(ctx.exception))

    def test_la_vraie_fonction_de_score_AVOUE_quand_elle_ne_peut_pas_mesurer(self):
        """Ce test disait l'inverse jusqu'au 27/08 : il vérifiait que
        score_hv_window ne produit JAMAIS de non-fini, ce qui justifiait la
        note « cas non atteignable par vol_strategy » dans hindsight_guard.py.

        C'était exact, et c'était le défaut. _sharpe rendait 0.0 sur moins de
        deux points et sur un écart-type nul — un zéro qui veut dire « je n'ai
        pas pu mesurer », indiscernable d'un Sharpe mesuré à zéro. Comme
        math.isfinite(0.0) est True, le garde `unscorable` ne voyait rien et
        certifiait des sélections où une fenêtre candidate n'avait jamais été
        notée.

        Le contrat est désormais l'inverse : sur une entrée dégénérée, la
        fonction de score doit rendre un NON-FINI, pas un chiffre inventé."""
        import vol_strategy
        import momentum_strategy
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
                    self.assertFalse(
                        math.isfinite(score),
                        "score_hv_window a rendu %r sur %r : une valeur fabriquée "
                        "que hindsight_guard prendra pour un résultat" % (score, nom))

        # momentum_strategy portait le défaut à l'identique (deux `return 0.0`
        # copiés). Sans cette boucle, seule la moitié serait verrouillée.
        #
        # « un prix a zero » est EXCLU ici, et c'est un point de fond, pas une
        # concession pour faire passer le test : momentum est en position en
        # permanence, donc sur ces 301 barres elle produit de vrais échantillons
        # et un vrai Sharpe (mesuré : 0,94). La stratégie de volatilité, elle,
        # n'entre que sur régime bon marché et n'a rien à mesurer. Le contrat
        # n'est pas « rendre un non-fini sur ces entrées-là », c'est « ne jamais
        # fabriquer un chiffre quand il n'y a rien à mesurer ». Assertion élargie
        # = test qui ment sur ce qu'il vérifie.
        for nom in ("aucune barre", "une barre", "prix plats"):
            with self.subTest(cas=nom, module="momentum"):
                self.assertFalse(
                    math.isfinite(momentum_strategy.score_lookback(10, "full", cas[nom])),
                    "momentum_strategy.score_lookback a rendu un fini sur %r" % nom)

    def test_une_fenetre_non_mesuree_empeche_la_certification(self):
        """Le témoin de bout en bout, avec la VRAIE fonction de score.

        325 barres au lieu des 592 exigées : la fenêtre 90 obtient zéro
        échantillon. Avant le 27/08, le garde répondait « OK: full-window
        winner (10) matches the in-sample winner and clears the threshold »."""
        import vol_strategy
        from vol_strategy import Bar, CANDIDATE_HV_WINDOWS
        from hindsight_guard import check_selection_leakage

        prix, barres, x = 100.0, [], 1
        for _ in range(325):
            x = (1103515245 * x + 12345) % (2 ** 31)
            prix *= 1.0 + ((x % 2001) - 1000) / 100000.0
            barres.append(Bar(close=prix))

        self.assertEqual(
            len(vol_strategy._vol_strategy_returns(barres, 90)), 0,
            "prérequis du test : la fenêtre 90 doit être sans échantillon ici")

        rapport = check_selection_leakage(
            CANDIDATE_HV_WINDOWS,
            lambda w, split: vol_strategy.score_hv_window(w, split, barres),
            threshold=0.0)
        self.assertIn(90, rapport.unscorable,
                      "la fenêtre 90, jamais notée, n'est pas signalée")
        self.assertFalse(rapport.agrees,
                         "le garde certifie une sélection où une fenêtre "
                         "candidate n'a jamais été notée")
        self.assertIn("CANNOT CONCLUDE", rapport.summary())



    # ------------------------------------------------------------------
    # Ajoutés le 27/08. Trois défauts du module PHARE, trouvés en le
    # sondant aux bords plutôt qu'en relisant sa logique centrale.
    # ------------------------------------------------------------------

    def test_le_verdict_ne_depend_pas_de_l_ordre_des_candidats(self):
        """LE défaut sérieux. `max()` rend le PREMIER élément atteignant le
        maximum, donc une égalité en tête faisait dépendre le gagnant de
        l'ordre de la liste. Mesuré, mêmes scores exactement :

            candidats ['A','B'] -> gagnant plein 'A', agrees=True
            candidats ['B','A'] -> gagnant plein 'B', agrees=False

        Même question, même fonction de score, verdict inversé. Et les deux
        sens sont atteignables : une égalité peut fabriquer un certificat
        « pas de fuite » aussi bien qu'une fausse alerte. Pour une
        bibliothèque qui existe pour refuser les certificats de complaisance,
        le premier sens est le grave.

        Non démontré atteignable sur les vraies barres de ce dépôt — deux
        Sharpe flottants qui tombent exactement égaux est improbable. Mais ce
        module est vendoré, MIT, publié à part et présenté comme la
        contribution du projet : un appelant dont le score est entier,
        arrondi, ou calculé sur des fenêtres dégénérées y arrive sans
        effort."""
        from hindsight_guard import check_selection_leakage
        def score(c, w):
            plein = {"A": 1.0, "B": 1.0}          # égalité en tête
            dedans = {"A": 1.0, "B": 0.5}
            return plein[c] if w == "full" else dedans[c]
        verdicts = {tuple(o): check_selection_leakage(list(o), score).agrees
                    for o in (("A", "B"), ("B", "A"))}
        self.assertEqual(len(set(verdicts.values())), 1,
                         "le verdict dépend de l'ordre de la liste : %s" % verdicts)

    def test_une_egalite_en_tete_ne_certifie_pas_l_absence_de_fuite(self):
        """Le sens dangereux, nommé à part. Si la fenêtre pleine est
        indifférente entre A et B, l'appelant peut retenir B — qui perd en
        in-sample. Ce choix-là dépend bien de données non connaissables, donc
        ce n'est pas certifiable, quel que soit l'ordre."""
        from hindsight_guard import check_selection_leakage
        def score(c, w):
            plein = {"A": 1.0, "B": 1.0}
            dedans = {"A": 1.0, "B": 0.5}
            return plein[c] if w == "full" else dedans[c]
        for ordre in (["A", "B"], ["B", "A"]):
            r = check_selection_leakage(ordre, score)
            self.assertFalse(r.agrees,
                             "égalité en tête certifiée sans fuite (ordre %s)" % ordre)

    def test_une_egalite_qui_ne_change_rien_reste_certifiable(self):
        """Pendant obligatoire : refuser TOUTE égalité rendrait le garde
        inutilisable. Si A gagne la fenêtre pleine seul et fait partie des
        gagnants in-sample, il n'y a pas de fuite — même si B l'y égale."""
        from hindsight_guard import check_selection_leakage
        def score(c, w):
            plein = {"A": 1.0, "B": 0.5}
            dedans = {"A": 1.0, "B": 1.0}
            return plein[c] if w == "full" else dedans[c]
        for ordre in (["A", "B"], ["B", "A"]):
            r = check_selection_leakage(ordre, score)
            self.assertTrue(r.agrees,
                            "une égalité sans conséquence est refusée (ordre %s)" % ordre)

    def test_le_resume_explique_l_egalite_au_lieu_de_se_contredire(self):
        """Le verdict corrigé ne suffit pas si son explication est
        incompréhensible. Mesuré juste après le correctif :

            LEAK DETECTED: ...
              full-window winner:      'A'  (score 1.0000)
              in-sample winner:        'A'  (score 1.0000)
              -> the two windows disagree about which candidate is best.

        Le même candidat nommé deux fois, et une phrase qui affirme un
        désaccord. Un juge qui lit ça conclut que l'outil est cassé — et il
        aurait raison de le penser. La vraie raison du refus est ailleurs :
        la fenêtre pleine ne départage pas A et B, et B perd en in-sample."""
        from hindsight_guard import check_selection_leakage
        def score(c, w):
            return {"A": 1.0, "B": 1.0}[c] if w == "full" else {"A": 1.0, "B": 0.5}[c]
        texte = check_selection_leakage(["A", "B"], score).summary()
        self.assertNotIn("the two windows disagree", texte,
                         "le résumé affirme un désaccord entre deux gagnants "
                         "identiques :\n%s" % texte)
        self.assertIn("'B'", texte,
                      "le candidat qui rend la sélection non certifiable n'est "
                      "même pas nommé :\n%s" % texte)
        self.assertIn("tie", texte.lower(),
                      "l'égalité, seule cause du refus, n'est pas dite :\n%s" % texte)

    def test_un_vrai_desaccord_est_toujours_decrit_comme_tel(self):
        """Pendant obligatoire : sans égalité, la phrase d'origine est juste
        et doit rester."""
        from hindsight_guard import check_selection_leakage
        def score(c, w):
            return {"A": 1.0, "B": 0.5}[c] if w == "full" else {"A": 0.2, "B": 0.9}[c]
        texte = check_selection_leakage(["A", "B"], score).summary()
        self.assertIn("the two windows disagree", texte)

    def test_un_score_non_numerique_nomme_le_candidat_et_la_fenetre(self):
        """`score_fn` qui rend None sur échec est l'erreur d'appelant la plus
        naturelle qui soit. Mesuré : `math.isfinite(None)` levait
        « TypeError: must be real number, not NoneType » — un message qui ne
        nomme NI le candidat NI la fenêtre.

        Pour une bibliothèque dont toute la thèse est « un candidat qu'on n'a
        pas pu noter n'est pas un candidat qui a perdu », échouer sans dire
        lequel est la mauvaise moitié du travail."""
        from hindsight_guard import check_selection_leakage
        def score(c, w):
            return None if c == 30 else 1.0
        with self.assertRaises(TypeError) as e:
            check_selection_leakage([10, 30, 90], score)
        message = str(e.exception)
        self.assertIn("30", message, "le candidat fautif n'est pas nommé : %s" % message)
        self.assertIn("full", message, "la fenêtre n'est pas nommée : %s" % message)

    def test_des_candidats_en_double_ne_disparaissent_pas_en_silence(self):
        """Mesuré : 3 candidats déclarés, 2 notés, agrees=True. Les scores
        vivent dans un dictionnaire indexé par candidat, donc un doublon
        s'écrase. Un balayage de N paramètres qui en teste discrètement M
        est exactement la panne silencieuse que ce module existe pour
        empêcher — ici dans son propre code."""
        from hindsight_guard import check_selection_leakage
        with self.assertRaises(ValueError) as e:
            check_selection_leakage(
                [10, 10, 90], lambda c, w: 1.0 if c == 10 else 0.5)
        self.assertIn("10", str(e.exception))


class HarnaisPlafonds:
    """Le décor commun aux tests de dimensionnement : un compte à équité
    fixe, un prix d'option stable, et de quoi fabriquer des positions
    ouvertes. Sorti en mixin le 26/08 : TestCoutIllisible en a besoin, et
    en héritant de TestPlafondsDeRisque il RÉ-EXÉCUTAIT ses sept tests —
    62 tests annoncés dont 7 doublons. Un compte de tests gonflé est une
    forme discrète du même problème que le reste de ce fichier traque."""

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




class TestPositionNonReconnueALaSortie(BaseExit):
    """Ajouté le 27/08, en relisant mon propre correctif d'une heure plus tôt.

    J'avais écrit que « les sorties ne passent pas par là » parce que
    manage_exits() lit list_positions() — toutes les positions — et non la
    liste filtrée. C'était imprécis : elle les lit toutes, puis FILTRE EN
    LIGNE, avec une copie de la même logique de reconnaissance :

        if "option" not in asset_class and not _OCC_PATTERN.match(symbol):
            continue

    Deux conséquences, et la seconde est la vraie :

    1. Le symbole n'est PAS normalisé ici (pas de .upper()), donc une écriture
       en minuscules échappe encore au motif — là où alpaca_cli le gère
       désormais. Deux copies de la même règle qui divergent.

    2. Une position non reconnue est écartée par un `continue` NU : aucune
       ExitAction, aucune ligne de journal, rien. Un P&L illisible produit au
       moins une action UNREADABLE visible ; une position qu'on ne classe pas
       ne produit AUCUNE trace. Or manage_exits est le seul mécanisme
       protégeant une position ouverte — Alpaca ne supporte pas les ordres
       bracket/OCO sur options.

    C'est le jumeau, côté sortie, du trou corrigé côté entrée. Et c'est le
    côté qui compte le plus."""

    @staticmethod
    def _pos(symbole, **extra):
        d = {"symbol": symbole, "cost_basis": "840.00", "qty": "1",
             "unrealized_plpc": "-0.60"}          # au-delà du stop-loss
        d.update(extra)
        return d

    def _actions(self, positions):
        self.positions = list(positions)
        return risk_gates.manage_exits(dry_run=True)

    def test_un_symbole_en_minuscules_est_toujours_gere(self):
        """L'assertion porte sur le KIND, pas sur « une action existe ».

        Première version : `assertTrue(actions)`. Une mutation l'a passée au
        vert en remettant la reconnaissance dupliquée — la position tombait
        alors dans la branche UNRECOGNISED, qui produit bien une action, et
        le test était satisfait. Or une position à −60 % doit être FERMÉE, pas
        signalée comme non classée. « Il s'est passé quelque chose » n'est pas
        « la bonne chose s'est passée »."""
        actions = self._actions([self._pos("spy260831p00764000")])
        self.assertTrue(
            actions,
            "une position au-delà de son stop-loss est ignorée parce que son "
            "symbole est en minuscules : aucune sortie, aucune trace")
        self.assertEqual(
            actions[0].kind, risk_gates.ExitKind.WOULD_CLOSE,
            "la position en minuscules est vue mais pas GÉRÉE (kind=%s) : son "
            "stop-loss n'est toujours pas appliqué" % actions[0].kind)

    def test_une_position_non_reconnue_laisse_une_trace(self):
        """Le point central. Écarter en silence une position qu'on ne sait pas
        classer, c'est décider qu'elle n'a pas besoin de stop-loss sans
        l'avoir vérifié."""
        actions = self._actions([self._pos("CONTRAT-INCONNU-42")])
        self.assertTrue(
            actions,
            "une position non reconnue disparaît sans une ligne : rien dans "
            "decision_log.jsonl, rien sur le tableau de bord")
        self.assertIn("CONTRAT-INCONNU-42", str(actions[0]))

    def test_une_action_ordinaire_reste_geree(self):
        """Témoin n°1 : une vraie action doit rester écartée en silence, sinon
        chaque passage journaliserait du bruit."""
        actions = self._actions([self._pos("AAPL", asset_class="us_equity")])
        self.assertEqual(
            actions, [],
            "une position actions ordinaire produit une alerte : le bruit "
            "permanent est ce qui apprend à ignorer un journal")

    def test_une_option_normale_est_toujours_fermee(self):
        """Témoin n°2 : le chemin nominal n'a pas bougé."""
        actions = self._actions([self._pos("SPY260831P00764000",
                                           asset_class="us_option")])
        self.assertTrue(actions)
        self.assertEqual(actions[0].kind, risk_gates.ExitKind.WOULD_CLOSE)



class TestPauseManuelleDansLaPorte(HarnaisPlafonds, BaseExit):
    """Ajouté le 27/08 au soir, la veille du kickoff — donc sur l'arrêt
    d'urgence que l'opérateur utilisera peut-être demain matin.

    Le README affirme, mot pour mot : « Creating a file named HALT at the repo
    root makes check_gates() refuse every new entry ». C'ÉTAIT FAUX. La pause
    était consultée par agent.py (ligne ~357), jamais par check_gates().

    Le comportement était correct — agent.py est aujourd'hui le seul appelant,
    et la pause fonctionnait bien de bout en bout. Mais la règle était
    appliquée par L'APPELANT et non par la porte censée l'appliquer : c'est la
    thèse de ce projet retournée contre lui, « une limite qui n'est pas
    vérifiée dans le code est une politique, pas un contrôle » (slide 6). Une
    pause qui dépend du fait que chaque appelant pense à la vérifier est une
    politique.

    La phrase est rendue VRAIE plutôt qu'affaiblie. agent.py garde sa
    vérification précoce — elle évite tout le travail d'évaluation — et la
    porte la refait, pour que tout appelant futur en hérite."""

    def _avec_halt(self, contenu):
        halt = self.tmp / "HALT"
        vrai = risk_gates.HALT_FILE
        risk_gates.HALT_FILE = halt
        try:
            if contenu is None:
                halt.unlink(missing_ok=True)
            else:
                halt.write_text(contenu, encoding="utf-8")
            return self._decide()
        finally:
            risk_gates.HALT_FILE = vrai

    def test_la_porte_refuse_quand_la_pause_est_posee(self):
        for contenu, etiquette in (("", "fichier vide"),
                                   ("incident réseau", "avec un motif"),
                                   ("   \n", "espaces seulement")):
            with self.subTest(cas=etiquette):
                d = self._avec_halt(contenu)
                self.assertFalse(
                    self._autorise(d),
                    "HALT présent (%s) et check_gates autorise quand même : "
                    "la pause n'est appliquée que par l'appelant" % etiquette)
                self.assertIn("HALT", d.reason or "",
                              "le refus ne nomme pas la pause : %s" % d.reason)

    def test_sans_pause_la_porte_laisse_passer(self):
        """Témoin : une porte qui refuse toujours ne protège rien."""
        d = self._avec_halt(None)
        self.assertTrue(self._autorise(d),
                        "aucun HALT et le trade est refusé : %s" % d.reason)

    def test_le_refus_dit_que_les_sorties_continuent(self):
        """L'asymétrie que ce projet promet partout : une pause bloque les
        NOUVELLES entrées, jamais la gestion des positions déjà ouvertes. Si
        le message ne le dit pas, un opérateur inquiet retire le HALT pour
        « débloquer les sorties » — et rouvre les entrées sans le vouloir."""
        d = self._avec_halt("incident")
        self.assertIn("xit", d.reason or "",
                      "le refus ne rassure pas sur les sorties : %s" % d.reason)

class TestIdentiteDeCompteInconnue(BaseExit):
    """Ajouté le 27/08, la veille du kickoff — donc sur le code qui ne
    s'exécutera qu'UNE fois, sans personne devant, à la bascule de compte.

    `bascule_de_compte = state.get("account_id") not in (None, account_id)`.
    Quand account_id vaut None — une réponse de compte sans champ « id » —
    l'expression devient `état_id not in (None,)`, donc VRAI. Un identifiant
    ILLISIBLE était traité exactement comme une vraie bascule.

    Reproduit, sur un état portant un verrou de perte ACTIF :

        même compte              -> verrou=True   pertes=2  sorties=1
        vraie bascule            -> verrou=False  pertes=0  sorties=0
        id illisible (None)      -> verrou=False  pertes=0  sorties=0

    Le verrou hebdomadaire effacé, le disjoncteur remis à zéro, la mémoire des
    sorties vidée, la référence d'équité redéfinie — sur une donnée qu'on n'a
    pas su lire. C'est la famille que ce fichier documente déjà mot pour mot :
    « silently cleared an active weekly loss lock ».

    Atteignabilité non démontrée en production — alpaca_cli.get_account() rend
    aujourd'hui un « id ». Mais ce dépôt documente DEUX surprises de nommage de
    ce CLI en « Alpha Preview », et « je n'ai pas su lire » n'autorise jamais à
    effacer une protection."""

    ETAT = {"account_id": "compte-A", "starting_equity": 100000.0,
            "locked": True, "lock_reason": "perte hebdomadaire de 3% atteinte",
            "consecutive_losses": 2, "exits_counted": {"SPY260831P00764000": True}}

    def _poser(self, account_id, etat=None):
        import contextlib, io
        etat = dict(etat if etat is not None else self.ETAT)
        with contextlib.redirect_stdout(io.StringIO()) as sortie:
            apres = risk_gates._record_starting_equity(100000.0, etat, account_id)
        return apres, sortie.getvalue()

    def test_un_identifiant_illisible_n_efface_aucune_protection(self):
        """Les trois formes d'illisible, pas seulement None.

        Ajouté après qu'une mutation soit restée verte : remplacer
        `account_id is None or not str(account_id).strip()` par le seul
        `is None` ne cassait aucun test, parce que mes témoins n'utilisaient
        que None. Une réponse portant `"id": ""` ou `"id": "  "` est tout
        aussi illisible, et effaçait tout de la même façon."""
        for illisible in (None, "", "   "):
            with self.subTest(id=repr(illisible)):
                apres, _ = self._poser(illisible)
                self.assertTrue(
                    apres.get("locked"),
                    "identifiant %r : le verrou a été effacé" % (illisible,))
                self.assertEqual(apres.get("consecutive_losses"), 2)
                self.assertEqual(apres.get("account_id"), "compte-A")

    def test_l_identifiant_illisible_est_annonce(self):
        _, sortie = self._poser(None)
        self.assertIn("WARNING", sortie.upper(),
                      "ne pas savoir sur quel compte on tourne passe en silence")

    def test_une_vraie_bascule_efface_toujours_tout(self):
        """Témoin n°1, et il compte : cette remise à zéro existe pour que
        l'oubli d'effacer state.json à la main ne fasse pas mesurer un
        drawdown contre l'équité d'un AUTRE compte."""
        apres, _ = self._poser("compte-B")
        self.assertFalse(apres.get("locked"))
        self.assertEqual(apres.get("consecutive_losses"), 0)
        self.assertEqual(apres.get("exits_counted"), {})
        self.assertEqual(apres.get("account_id"), "compte-B")

    def test_le_meme_compte_ne_touche_a_rien(self):
        """Témoin n°2."""
        apres, _ = self._poser("compte-A")
        self.assertTrue(apres.get("locked"))
        self.assertEqual(apres.get("consecutive_losses"), 2)

    def test_un_tout_premier_passage_reste_possible(self):
        """Témoin n°3, le plus important pour ne pas fabriquer une panne : sur
        un état VIERGE, il n'y a aucune protection à préserver. Refuser là
        empêcherait l'agent de poser sa référence d'équité, donc de démarrer,
        y compris quand tout va bien."""
        apres, _ = self._poser(None, etat={})
        self.assertEqual(apres.get("starting_equity"), 100000.0,
                         "un premier passage ne peut plus poser sa référence "
                         "d'équité : l'agent ne démarrerait jamais")

class TestSymboleOCCNonReconnu(HarnaisPlafonds, BaseExit):
    """Ajouté le 27/08. La règle « jamais deux positions sur le même
    sous-jacent » — énoncée dans le deck, le write-up et le script vidéo —
    cédait sur une forme de symbole parfaitement standard.

    OCC définit un symbole de 21 caractères dont la racine est COMPLÉTÉE PAR
    DES ESPACES : « SPY   260831P00764000 ». Alpaca renvoie généralement la
    forme compacte, mais rien ne le garantit, et alpaca_cli.py documente
    lui-même son incertitude sur les champs du CLI (« not yet verified
    whether the CLI's `position list` output includes it too »).

    Mesuré de bout en bout, MÊME position, deux écritures :

        OCC compact  -> refuse : « already holding an open option position »
        OCC standard -> AUTORISE un 2e SPY, dimensionne 3 contrats

    C'est la signature exacte du trou déjà documenté dans check_gates
    (« TROU REPRODUIT », ligne ~1219) : l'exposition totale reste juste, seule
    la règle anti-doublon cède. Mais cette route-ci ne demande QU'UNE
    condition, là où l'autre en demandait deux.

    Deux correctifs distincts, et le second compte plus que le premier :
    reconnaître la forme standard ferme la porte connue ; REFUSER quand le
    sous-jacent d'une position ouverte est illisible ferme toutes les
    autres — même logique que positions_au_cout_illisible()."""

    OCC_COMPACT = "SPY260831P00764000"
    OCC_STANDARD = "SPY   260831P00764000"      # 21 car., racine complétée

    def test_la_forme_standard_est_reconnue_comme_une_option(self):
        for sym in (self.OCC_COMPACT, self.OCC_STANDARD,
                    self.OCC_COMPACT.lower()):
            with self.subTest(symbole=repr(sym)):
                self.assertTrue(
                    alpaca_cli.is_option_position({"symbol": sym}),
                    "%r n'est pas reconnu comme une option : la position "
                    "disparaît de toutes les vérifications d'entrée" % sym)

    def test_le_sous_jacent_est_lisible_dans_les_deux_formes(self):
        for sym in (self.OCC_COMPACT, self.OCC_STANDARD,
                    self.OCC_COMPACT.lower()):
            with self.subTest(symbole=repr(sym)):
                self.assertEqual(
                    alpaca_cli.option_underlying({"symbol": sym}), "SPY",
                    "sous-jacent illisible pour %r" % sym)

    def test_pas_de_second_spy_quelle_que_soit_l_ecriture(self):
        """Le test qui compte : la conséquence, pas la cause."""
        for sym in (self.OCC_COMPACT, self.OCC_STANDARD):
            with self.subTest(symbole=repr(sym)):
                d = self._decide([self._ouverte(sym, 840.0)],
                                 sous_jacent="SPY",
                                 option="SPY260905P00760000")
                self.assertFalse(
                    self._autorise(d),
                    "une 2e position SPY est autorisée alors qu'une est "
                    "ouverte, écrite %r : %s" % (sym, d.reason))

    def test_un_sous_jacent_illisible_ferme_la_porte(self):
        """Le correctif durable. Reconnaître la forme standard ne ferme que
        la porte qu'on a trouvée. Si le sous-jacent d'une position OUVERTE
        reste illisible — un format qu'on n'a pas prévu — on ne peut pas
        vérifier la règle anti-doublon, donc on ne trade pas. « Je n'ai pas
        compris » n'est pas « il n'y a rien » : c'est exactement l'argument
        que porte déjà list_positions()."""
        mystere = {"symbol": "CONTRAT-INCONNU-42", "asset_class": "us_option",
                   "cost_basis": "840.00", "qty": "1"}
        d = self._decide([mystere], sous_jacent="SPY",
                         option="SPY260905P00760000")
        self.assertFalse(
            self._autorise(d),
            "une position ouverte dont le sous-jacent est ILLISIBLE est "
            "ignorée, et le trade passe : %s" % d.reason)
        self.assertIn("CONTRAT-INCONNU-42", d.reason or "",
                      "le refus ne nomme pas la position fautive : %s" % d.reason)

    def test_un_sous_jacent_different_reste_autorise(self):
        """Pendant obligatoire : si toute position ouverte bloquait tout, le
        projet ne pourrait plus tenir ses 4 positions simultanées annoncées."""
        d = self._decide([self._ouverte(self.OCC_STANDARD, 840.0)],
                         sous_jacent="XLV", option="XLV260831C00150000")
        self.assertTrue(self._autorise(d),
                        "un sous-jacent différent est refusé à tort : %s" % d.reason)

class TestPlafondsDeRisque(HarnaisPlafonds, BaseExit):
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


class TestDoublonDansUneMemeExecution(BaseExit):
    """Deux entrées sur le même sous-jacent dans une seule exécution.

    LE TROU, reproduit. Il demandait DEUX conditions, et les deux sont
    atteignables :

      1. le même symbole deux fois dans la liste. `agent.py` faisait
         `[s.strip().upper() for s in args.symbols.split(",")]` sans
         dédoublonner — `--symbols SPY,SPY` suffisait.
      2. l'échec de `record_order_submitted()`, cas qu'`agent.py` prévoit
         explicitement, signale par un avertissement, et après lequel il
         CONTINUE. Sans cet enregistrement, le garde `traded_today` de
         state.json ne rattrape plus rien.

    Le contrôle anti-doublon de `check_gates` ne consultait alors que l'API —
    laquelle, pendant la fenêtre de latence, ne voit pas encore la position
    ouverte une seconde plus tôt. Résultat mesuré : deux ordres sur SPY, contre
    une règle que ce projet énonce comme non négociable.

    RASSURANT SUR LE RESTE : l'accumulateur d'exposition TOTALE fonctionnait
    pendant ce trou — le second passage dimensionnait 2 contrats au lieu de 3,
    il savait donc que 840 $ étaient déjà engagés. Seule la règle anti-doublon
    cédait. Les deux tests ci-dessous épinglent cette distinction.
    """

    EQUITE = 100000.0

    def setUp(self):
        super().setUp()
        alpaca_cli.get_account = lambda: {
            "id": "compte-test", "equity": str(self.EQUITE),
            "portfolio_value": str(self.EQUITE)}
        alpaca_cli.get_option_ask_price = lambda s: 2.80
        self.positions = []          # l'API n'a pas encore rattrapé

    def test_le_meme_sous_jacent_deux_fois_dans_un_run_est_bloque(self):
        """Sans jamais enregistrer dans state.json — le pire cas."""
        engages, ouverts = {}, set()

        premier = risk_gates.check_gates(
            "SPY", "SPY260831C00500000",
            already_committed_this_run_by_underlying=engages,
            already_open_this_run_underlyings=ouverts)
        self.assertTrue(getattr(premier, "allowed", False))
        engages["SPY"] = premier.committed_dollars
        ouverts.add("SPY")
        # record_order_submitted() n'est PAS appelé : on simule son échec.

        second = risk_gates.check_gates(
            "SPY", "SPY260831C00500000",
            already_committed_this_run_by_underlying=engages,
            already_open_this_run_underlyings=ouverts)
        self.assertFalse(getattr(second, "allowed", False),
                         "deux ordres sur le même sous-jacent dans une seule exécution")
        self.assertIn("THIS run", str(getattr(second, "reason", "")))

    def test_l_accumulateur_d_exposition_totale_fonctionnait_deja(self):
        """Contre-épreuve : ne pas attribuer au correctif un mérite qui n'est
        pas le sien. Un AUTRE sous-jacent doit passer, mais dimensionné à la
        baisse par ce qui a déjà été engagé ce run."""
        second = risk_gates.check_gates(
            "XLV", "XLV260831C00150000",
            already_committed_this_run_by_underlying={"SPY": 2500.0},
            already_open_this_run_underlyings={"SPY"})
        self.assertTrue(getattr(second, "allowed", False),
                        "un autre sous-jacent est bloqué à tort")
        self.assertIn("1 contract", str(getattr(second, "reason", "")),
                      "500 $ restants sous le plafond total : un seul contrat")


class TestDeduplicationDesSymboles(unittest.TestCase):
    """`--symbols SPY,SPY` ne doit pas évaluer SPY deux fois.

    `dict.fromkeys` dédoublonne EN GARDANT L'ORDRE, contrairement à `set()` —
    l'ordre compte ici, puisque le budget se consomme au fil de la boucle et
    que le premier symbole servi a plus de place que le dernier.
    """

    @staticmethod
    def _analyse(brut):
        # même expression que agent.py
        return list(dict.fromkeys(
            s.strip().upper() for s in brut.split(",") if s.strip()))

    def test_les_doublons_disparaissent(self):
        self.assertEqual(self._analyse("SPY,SPY"), ["SPY"])
        self.assertEqual(self._analyse("spy,SPY, SPY "), ["SPY"])

    def test_l_ordre_est_preserve(self):
        """set() casserait ça, et l'ordre décide de qui obtient le budget."""
        self.assertEqual(self._analyse("SPY,GLD,SPY,XLK"), ["SPY", "GLD", "XLK"])
        self.assertEqual(self._analyse("XLV,XLK,GLD,SPY"), ["XLV", "XLK", "GLD", "SPY"])

    def test_agent_py_utilise_bien_cette_expression(self):
        """Un test qui recopie la logique ne vaut que s'il est relié au code.

        Le fichier est lu SUR LE DISQUE, pas via `inspect.getsource`.
        `inspect` passe par `linecache`, qui met la source en cache dès le
        premier import du module : le test mesurait alors l'instantané du
        début de session, pas l'état courant. Vérifié par mutation — retirer
        `dict.fromkeys` d'agent.py laissait ce test VERT.
        """
        import pathlib
        source = (pathlib.Path(__file__).parent / "agent.py").read_text(encoding="utf-8")
        # On cherche l'AFFECTATION complète, pas le nom seul. Première version :
        # `assertIn("dict.fromkeys", source)` — qui passait encore après avoir
        # retiré l'appel, parce que le COMMENTAIRE juste au-dessus explique
        # pourquoi `dict.fromkeys` est utilisé. Un test satisfait par un
        # commentaire ne teste rien. Trouvé par mutation.
        self.assertIn("symbols = list(dict.fromkeys(", source,
                      "agent.py ne dédoublonne plus la liste de symboles")


class TestVerrouDePerte(BaseExit):
    """Le verrou de repli — et ce que son nom ne dit pas.

    Il s'appelle `WEEKLY_LOSS_LOCK_PCT`, et le README parlait d'un « 3% weekly
    drawdown lock ». Mesuré le 26/08 : **il n'est pas hebdomadaire**. Il compare
    à `starting_equity`, posée une fois par compte et jamais rebaselinée
    autrement que sur un changement de compte. Aucune logique de frontière de
    semaine n'existe dans le fichier — ni `isocalendar`, ni `weekday`, ni date
    de référence dans `state.json`.

    Le comportement est GARDÉ, parce qu'il penche du bon côté : il ne se
    relâche jamais seul, comme le disjoncteur de pertes consécutives. Ces tests
    épinglent ce qu'il fait réellement, pour qu'un futur « correctif » qui
    ajouterait une remise à zéro hebdomadaire soit un choix délibéré et non un
    glissement — et pour que le prochain lecteur ne soit pas trompé par le nom.
    """

    def setUp(self):
        super().setUp()
        self.equite = [100000.0]
        alpaca_cli.get_account = lambda: {
            "id": "compte-test", "equity": str(self.equite[0]),
            "portfolio_value": str(self.equite[0])}
        alpaca_cli.get_option_ask_price = lambda s: 2.80
        self.positions = []

    def _decide(self, equite):
        self.equite[0] = equite
        d = risk_gates.check_gates("SPY", "SPY260831C00500000")
        return bool(getattr(d, "allowed", False)), str(getattr(d, "reason", ""))

    def test_le_verrou_se_declenche_au_dela_du_seuil(self):
        self.assertTrue(self._decide(100000.0)[0], "la référence doit être posée sans blocage")
        self.assertTrue(self._decide(97500.0)[0], "-2,5% est sous le seuil de 3%")
        autorise, raison = self._decide(96000.0)
        self.assertFalse(autorise, "-4% doit déclencher le verrou")
        self.assertIn("loss lock", raison)

    def test_le_verrou_est_collant_meme_si_l_equite_remonte(self):
        """« Une mauvaise passe arrête vraiment l'agent » — pas jusqu'au
        prochain rebond."""
        self._decide(100000.0)
        self._decide(96000.0)                       # déclenche
        autorise, raison = self._decide(100000.0)   # tout est revenu
        self.assertFalse(autorise, "le verrou s'est relâché tout seul")
        self.assertIn("already active", raison)

    def test_un_state_corrompu_ne_devErrouille_pas(self):
        """Un plantage en pleine écriture ne doit pas dé-pauser un agent qui
        devait avoir cessé de trader."""
        self._decide(100000.0)
        self._decide(96000.0)
        risk_gates.STATE_FILE.write_text('{"locked": true, "starting_equ', encoding="utf-8")
        autorise, raison = self._decide(100000.0)
        self.assertFalse(autorise)
        self.assertIn("corrupted", raison)

    def test_la_reference_ne_suit_PAS_le_sommet_ni_la_semaine(self):
        """Le point que le nom cache. Ce test échouera si quelqu'un ajoute un
        jour une vraie remise à zéro hebdomadaire ou un suivi du sommet — et
        c'est voulu : ce serait un changement de politique, pas un détail."""
        self.assertTrue(self._decide(100000.0)[0])   # référence = 100 000
        self.assertTrue(self._decide(110000.0)[0])   # +10%

        # -4,5% depuis le sommet, mais toujours au-dessus de la référence.
        autorise, _ = self._decide(105000.0)
        self.assertTrue(
            autorise,
            "le verrou s'est déclenché sur une baisse depuis le SOMMET : la "
            "référence a changé de sens, ce que le code ne fait pas aujourd'hui")

        # -3,5% depuis la référence d'origine : là, il doit bloquer.
        self.assertFalse(self._decide(96500.0)[0])

    def test_aucune_date_de_reference_n_est_stockee(self):
        """Corollaire direct : rien dans l'état ne permettrait une remise à
        zéro hebdomadaire. Si une clé de date apparaît un jour, ce test le
        signale — il faudra alors décider explicitement du comportement."""
        self._decide(100000.0)
        etat = self.etat()
        cles_de_date = [k for k in etat
                        if k != "traded_today" and ("week" in k or "date" in k)]
        self.assertEqual(cles_de_date, [],
                         "une clé de date est apparue dans state.json : le "
                         "verrou est-il devenu réellement hebdomadaire ?")


class TestEcrituresConcurrentes(unittest.TestCase):
    """Deux processus écrivent state.json : agent.py (une fois par jour) et
    monitor_exits.py (tous les quarts d'heure, via launchd). L'écriture est
    atomique depuis le 24/08 — fichier temporaire + os.replace — donc un
    lecteur ne voit jamais un fichier à moitié écrit.

    L'atomicité empêche un fichier DÉCHIRÉ. Elle n'empêche pas une MISE À JOUR
    PERDUE, qui est une panne différente, et la seule réellement atteignable
    ici : chacun lit, modifie sa copie, écrit ; le second écrasement efface la
    mise à jour du premier.

    Mesuré le 26/08 avant correctif, en entrelaçant les deux écrivains publics
    avec une lecture ralentie (la fenêtre existe déjà — la pause l'élargit, elle
    ne l'invente pas) : consecutive_losses retombait à 0. Le disjoncteur de
    pertes sous-comptait. Pas de plantage, pas de corruption, aucun message.

    C'est la panne que la gestion de corruption avait été écrite pour empêcher
    (« un plantage aurait dé-pausé en silence un agent censé s'être arrêté »),
    sauf qu'aucun plantage n'est nécessaire : deux écritures normales suffisent.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hindsight-conc-"))
        self._vrai_state_file = risk_gates.STATE_FILE
        self._vrai_load = risk_gates._load_state
        risk_gates.STATE_FILE = self.tmp / "state.json"
        risk_gates.STATE_FILE.write_text(json.dumps({
            "account_id": "compte-test", "starting_equity": 100000.0,
            "locked": False, "consecutive_losses": 0,
            "traded_today": {"date": risk_gates._today(), "symbols": []},
        }), encoding="utf-8")

    def tearDown(self):
        risk_gates.STATE_FILE = self._vrai_state_file
        risk_gates._load_state = self._vrai_load
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ralentir_la_lecture(self, secondes=0.30):
        vrai = self._vrai_load

        def load_lent():
            etat = vrai()
            time.sleep(secondes)
            return etat

        risk_gates._load_state = load_lent

    def etat(self):
        return json.loads(risk_gates.STATE_FILE.read_text(encoding="utf-8"))

    def test_deux_ecrivains_entrelaces_ne_se_perdent_pas(self):
        """Le test qui mord : lancé contre le code d'avant le verrou, il rend
        consecutive_losses=0 au lieu de 1."""
        self._ralentir_la_lecture()
        erreurs = []

        def enregistre_ordre():
            try:
                risk_gates.record_order_submitted("SPY")
            except Exception as err:            # pragma: no cover - diagnostic
                erreurs.append(err)

        def enregistre_perte():
            try:
                risk_gates._record_exit_outcome(is_win=False)
            except Exception as err:            # pragma: no cover - diagnostic
                erreurs.append(err)

        fils = [threading.Thread(target=enregistre_ordre),
                threading.Thread(target=enregistre_perte)]
        for f in fils:
            f.start()
        for f in fils:
            f.join(timeout=30)

        # Les assertions d'ÉTAT d'abord, les exceptions ensuite : sur le code
        # d'avant le verrou, les deux écrivains se disputent aussi le même
        # fichier temporaire (`state.json.tmp`, nom fixe), et l'un voit
        # disparaître celui de l'autre sous son os.replace(). Ce FileNotFoundError
        # est un SECOND bug de concurrence, corrigé par le même verrou -- mais
        # s'il est asserté en premier, il masque la panne que ce test annonce.
        etat = self.etat()
        self.assertEqual(etat["traded_today"]["symbols"], ["SPY"],
                         "le garde anti-doublon a oublié SPY : l'écriture de "
                         "l'autre processus a écrasé la sienne")
        self.assertEqual(etat.get("consecutive_losses"), 1,
                         "la perte n'est plus comptée : le disjoncteur "
                         "sous-compte à cause d'une mise à jour perdue")
        self.assertEqual(erreurs, [], "un écrivain a levé une exception")

    def test_le_verrou_exclut_reellement(self):
        """Sans ceci, remplacer le corps de _state_lock par un `yield` nu
        passerait inaperçu — le test précédent redeviendrait rouge, celui-ci
        dit POURQUOI."""
        obtenu_par_le_second = []

        def second():
            try:
                with risk_gates._state_lock(timeout_s=0.2):
                    obtenu_par_le_second.append("obtenu")
            except risk_gates.StateLockUnavailable:
                obtenu_par_le_second.append("refusé")

        with risk_gates._state_lock():
            f = threading.Thread(target=second)
            f.start()
            f.join(timeout=30)

        self.assertEqual(obtenu_par_le_second, ["refusé"],
                         "un second détenteur a obtenu le verrou alors que le "
                         "premier le tenait : le verrou ne verrouille rien")

    def test_le_verrou_est_relache_meme_si_le_corps_leve(self):
        """Un verrou qui survit à une exception fige l'agent pour de bon."""
        with self.assertRaises(ZeroDivisionError):
            with risk_gates._state_lock():
                1 / 0
        with risk_gates._state_lock(timeout_s=0.5):
            pass  # doit être obtenable : si on arrive ici, il a bien été relâché


class TestCoutIllisible(HarnaisPlafonds, BaseExit):
    """Une position ouverte dont on ne sait pas lire le montant engagé.

    _total_committed() la comptait pour ZÉRO dollar — choix explicite dans son
    docstring (« counting as 0 [...] doesn't block sizing »). Donc une donnée
    illisible AGRANDISSAIT le budget de risque au lieu de le fermer.

    Mesuré le 26/08, équité $100 000, plafond global 3 % :
        3 positions à $900   lisibles   -> taille 1 contrat
        les MÊMES            illisibles -> taille 3 contrats
        3 positions à $2 900 lisibles   -> REFUSE (8,7 % déjà exposé)
        les MÊMES            illisibles -> ouvre une position pleine

    La porte refusait correctement dès qu'elle savait lire. Elle cessait
    d'exister exactement quand l'agent avait perdu la trace de son exposition.
    """

    def _illisible(self, symbole, montant=900.0):
        pos = self._ouverte(symbole, montant)
        del pos["cost_basis"]
        return pos

    def test_un_cout_illisible_refuse_l_entree_nouvelle(self):
        """Mord : avant correctif, ces trois positions donnaient AUTORISE."""
        d = self._decide([self._illisible(s) for s in ("AAA260831C00100000", "BBB260831C00100000", "CCC260831C00100000")])
        self.assertFalse(self._autorise(d),
                         "une entrée a été autorisée alors que l'exposition "
                         "totale était illisible")
        self.assertIn("cost_basis", d.reason)

    def test_une_seule_position_illisible_suffit(self):
        """Le budget est une SOMME : un seul terme manquant la fausse."""
        positions = [self._ouverte("AAA260831C00100000", 900.0), self._ouverte("BBB260831C00100000", 900.0),
                     self._illisible("CCC260831C00100000")]
        d = self._decide(positions)
        self.assertFalse(self._autorise(d))
        self.assertIn("CCC260831C00100000", d.reason,
                      "le refus ne nomme pas la position fautive")

    def test_le_refus_n_est_pas_aveugle(self):
        """Contrôle : sans ce test, refuser TOUJOURS passerait le test du
        dessus. Des montants lisibles doivent continuer à passer."""
        d = self._decide([self._ouverte(s, 900.0) for s in ("AAA260831C00100000", "BBB260831C00100000")])
        self.assertTrue(self._autorise(d),
                        "des montants parfaitement lisibles sont refusés")

    def test_les_sorties_ne_sont_pas_affectees(self):
        """La promesse écrite dans le message de refus : « Exits are
        unaffected ». Une position en perte doit rester fermable même si son
        cost_basis est illisible — la sortie se décide sur unrealized_plpc, pas
        sur le montant engagé. Si ce test tombe, le correctif a transformé une
        entrée refusée en position qu'on ne peut plus fermer."""
        perdante = self._illisible("AAA260831C00100000")
        perdante["unrealized_plpc"] = "-0.55"
        self.positions = [perdante]
        actions = risk_gates.manage_exits(dry_run=False)
        self.assertTrue(actions, "aucune sortie déclenchée sur une position "
                                 "à -55 % dont le coût est illisible")


class TestQualiteDesBarres(unittest.TestCase):
    """_check_bar_quality attrapait un feed GELÉ (barre la plus récente trop
    vieille) et un feed CORROMPU (saut de prix invraisemblable). Il n'attrapait
    pas un feed TRONQUÉ.

    Mesuré le 27/08 : avec 325 barres au lieu des 592 qu'exige
    MIN_TRADING_DAYS_FOR_SWEEP, la fenêtre HV de 90 jours obtient zéro
    échantillon — et la sélection se faisait parmi des candidates dont
    certaines n'avaient jamais été mesurées.
    """

    @staticmethod
    def _lignes(n, avec_cloture=True, prix=100.0):
        maintenant = datetime.now(timezone.utc).isoformat()
        lignes = []
        for i in range(n):
            ligne = {"t": maintenant}
            if avec_cloture:
                ligne["c"] = prix + (i % 3) * 0.01   # variation minime, aucun saut
            lignes.append(ligne)
        return lignes

    def test_trop_peu_de_barres_est_refuse(self):
        with self.assertRaises(alpaca_cli.DataQualityError) as ctx:
            alpaca_cli._check_bar_quality("SPY", self._lignes(325), minimum_usable=592)
        message = str(ctx.exception)
        self.assertIn("325", message)
        self.assertIn("592", message)

    def test_assez_de_barres_passe(self):
        """Contrôle : sans lui, refuser toujours passerait le test du dessus."""
        alpaca_cli._check_bar_quality("SPY", self._lignes(592), minimum_usable=592)

    def test_les_lignes_sans_cloture_ne_comptent_pas(self):
        """get_daily_bars écarte silencieusement toute ligne sans prix de
        clôture. Compter les LIGNES plutôt que les clôtures exploitables
        laisserait donc passer un feed qui a la bonne longueur et pas les
        données."""
        lignes = self._lignes(592, avec_cloture=False)
        with self.assertRaises(alpaca_cli.DataQualityError) as ctx:
            alpaca_cli._check_bar_quality("SPY", lignes, minimum_usable=592)
        self.assertIn("0 usable", str(ctx.exception))

    def test_un_prix_nul_est_refuse(self):
        """Un prix de clôture nul ou négatif est impossible pour un ETF.

        Personne ne le signalait, et deux endroits l'évitaient chacun de leur
        côté sans le dire : la boucle de saut fait `if prev == 0: continue`, et
        vol_strategy.daily_returns() filtre `closes[i-1] != 0`. Une barre à
        zéro traversait donc le contrôle qualité puis disparaissait de la série
        de rendements, recollant artificiellement les deux jours qui
        l'entouraient — un rendement inventé sur des données fausses."""
        lignes = self._lignes(10)
        lignes[4]["c"] = 0.0
        with self.assertRaises(alpaca_cli.DataQualityError) as ctx:
            alpaca_cli._check_bar_quality("SPY", lignes)
        self.assertIn("non-positive", str(ctx.exception))

    def test_un_prix_negatif_est_refuse(self):
        lignes = self._lignes(10)
        lignes[7]["c"] = -3.5
        with self.assertRaises(alpaca_cli.DataQualityError):
            alpaca_cli._check_bar_quality("SPY", lignes)

    def test_des_prix_normaux_passent(self):
        """Contrôle : sans lui, refuser tout passerait les deux tests ci-dessus."""
        alpaca_cli._check_bar_quality("SPY", self._lignes(10))

    def test_sans_minimum_le_controle_ne_s_applique_pas(self):
        """get_last_price() demande 5 barres ; les autres appelants passent
        leur propre horizon. Un minimum non fourni ne doit rien refuser."""
        alpaca_cli._check_bar_quality("SPY", self._lignes(3))

    def test_get_daily_bars_transmet_bien_l_horizon_demande(self):
        """Sans cette transmission, le contrôle existerait sans jamais servir —
        exactement la forme d'échec que ce fichier traque."""
        vus = {}
        vrai_run = alpaca_cli.run
        vrai_check = alpaca_cli._check_bar_quality
        alpaca_cli.run = lambda args: {"bars": self._lignes(600)}

        def espion(symbol, rows, minimum_usable=None):
            vus["minimum"] = minimum_usable
            return vrai_check(symbol, rows, minimum_usable)

        alpaca_cli._check_bar_quality = espion
        try:
            alpaca_cli.get_daily_bars("SPY", lookback_days=42)
        finally:
            alpaca_cli.run = vrai_run
            alpaca_cli._check_bar_quality = vrai_check
        self.assertEqual(vus.get("minimum"), 42,
                         "get_daily_bars ne transmet pas son horizon au contrôle "
                         "qualité : le contrôle ne s'appliquerait jamais")


class TestBarresDuBonSymbole(unittest.TestCase):
    """Ajouté le 27/08. _extract_bars() gère deux formes de réponse connues :
    {"bars": [...]} et {"bars": {"SYMBOLE": [...]}}. Dans le second cas elle
    prenait la PREMIÈRE valeur du dictionnaire, sans jamais regarder la clé.

    Reproduit : une réponse portant la clé « GLD » pour une demande « SPY »
    rendait 700 barres d'or, sans erreur ni avertissement. SPY aurait été
    évalué, noté par hindsight_guard et tradé sur des prix d'or — et rien,
    nulle part, n'aurait pu le signaler. Le garde de fuite tourne parfaitement
    sur des données qui ne sont pas les bonnes.

    ATTEIGNABILITÉ NON DÉMONTRÉE : l'appel passe --symbol, donc une API qui se
    comporte bien ne peut renvoyer que ce symbole. Mais ce fichier documente
    DÉJÀ deux surprises de nommage de ce CLI en « Alpha Preview » (--symbols
    au pluriel pour les snapshots d'options, --symbol-or-asset-id pour la
    clôture), et une réponse multi-symboles rendrait ici un symbole arbitraire
    selon l'ordre du dictionnaire.

    Le coût du contrôle est d'une ligne ; celui de son absence est de trader
    le mauvais instrument. C'est l'asymétrie autour de laquelle tout ce
    projet est construit."""

    @staticmethod
    def _barres(depart, n=700):
        from datetime import datetime, timedelta, timezone
        maintenant = datetime.now(timezone.utc)
        return [{"t": (maintenant - timedelta(days=n - i)).isoformat(),
                 "c": depart + i * 0.01} for i in range(n)]

    def _demander(self, reponse, symbole="SPY"):
        from unittest import mock
        with mock.patch.object(alpaca_cli, "run", lambda a: reponse):
            return alpaca_cli.get_daily_bars(symbole, lookback_days=600)

    def test_une_reponse_portant_un_autre_symbole_est_refusee(self):
        with self.assertRaises(alpaca_cli.AlpacaCLIError) as e:
            self._demander({"bars": {"GLD": self._barres(300.0)}}, "SPY")
        message = str(e.exception)
        self.assertIn("SPY", message, "le symbole demandé n'est pas nommé")
        self.assertIn("GLD", message, "le symbole reçu n'est pas nommé")

    def test_une_reponse_multi_symboles_ne_prend_pas_le_premier_venu(self):
        """Le cas le plus insidieux : le bon symbole EST là, mais pas en
        premier. Prendre `next(iter(...))` rendait de l'or."""
        reponse = {"bars": {"GLD": self._barres(300.0),
                            "SPY": self._barres(760.0)}}
        barres = self._demander(reponse, "SPY")
        self.assertAlmostEqual(barres[0].close, 760.0, places=2,
                               msg="les barres d'un autre symbole ont été "
                                   "retenues alors que SPY était présent")

    def test_la_forme_a_un_seul_symbole_reste_acceptee(self):
        """Témoin n°1 : la forme {"bars": {"SPY": [...]}}, la plus courante."""
        barres = self._demander({"bars": {"SPY": self._barres(760.0)}}, "SPY")
        self.assertAlmostEqual(barres[0].close, 760.0, places=2)

    def test_la_forme_sans_dictionnaire_reste_acceptee(self):
        """Témoin n°2 : {"bars": [...]} n'a pas de clé de symbole à vérifier.
        Exiger une clé partout casserait la forme mono-symbole de l'API."""
        barres = self._demander({"bars": self._barres(760.0)}, "SPY")
        self.assertAlmostEqual(barres[0].close, 760.0, places=2)

    def test_la_casse_du_symbole_n_est_pas_un_motif_de_refus(self):
        """Un refus sur « spy » vs « SPY » serait un faux positif, et un
        contrôle qui crie sur du normal s'apprend à ignorer."""
        barres = self._demander({"bars": {"spy": self._barres(760.0)}}, "SPY")
        self.assertAlmostEqual(barres[0].close, 760.0, places=2)


class TestChoixDuContrat(unittest.TestCase):
    """find_near_the_money_contract choisissait le strike délibérément et
    l'échéance pas du tout.

    Sa clé de tri ne regardait que |strike - spot|. La requête couvre 7 à 21
    jours, et un sous-jacent liquide a des échéances lundi/mercredi/vendredi :
    une demi-douzaine de contrats partagent donc exactement le même strike, et
    min() rendait le premier de la liste.

    Mesuré le 27/08, même spot, mêmes contrats, même strike retenu :
        ordre API croissant   -> échéance à  2 jours
        ordre API inverse     -> échéance à 15 jours
        ordre API quelconque  -> échéance à 11 jours

    La valeur temps de ce qui est acheté dépendait d'un détail que l'API ne
    spécifie pas, sur CHAQUE transaction.
    """

    SPOT = 500.0
    ECHEANCES = ["2026-09-02", "2026-09-04", "2026-09-08", "2026-09-11", "2026-09-15"]

    def setUp(self):
        self._vrai_run = alpaca_cli.run

    def tearDown(self):
        alpaca_cli.run = self._vrai_run

    def _contrats(self, echeances, strikes=(495.0, 500.0, 505.0)):
        out = []
        for exp in echeances:
            for k in strikes:
                out.append({
                    "symbol": "SPY%sC%08d" % (exp.replace("-", "")[2:], int(k * 1000)),
                    "strike_price": str(k),
                    "expiration_date": exp,
                })
        return out

    def _choisir(self, contrats):
        alpaca_cli.run = lambda args: {"option_contracts": contrats}
        return alpaca_cli.find_near_the_money_contract("SPY", +1, spot=self.SPOT)

    def test_le_choix_ne_depend_pas_de_l_ordre_de_la_reponse(self):
        ordres = [
            self.ECHEANCES,
            list(reversed(self.ECHEANCES)),
            [self.ECHEANCES[3], self.ECHEANCES[0], self.ECHEANCES[4],
             self.ECHEANCES[1], self.ECHEANCES[2]],
        ]
        choix = {self._choisir(self._contrats(o)) for o in ordres}
        self.assertEqual(len(choix), 1,
                         "le contrat acheté change avec le seul ordre de la "
                         "réponse de l'API : %r" % sorted(choix))

    def test_le_strike_prime_toujours_sur_l_echeance(self):
        """Sans ceci, départager d'abord par échéance passerait le test du
        dessus tout en achetant un strike plus éloigné du spot."""
        contrats = (
            self._contrats(["2026-09-02"], strikes=(520.0,))   # proche, mais loin du spot
            + self._contrats(["2026-09-15"], strikes=(500.0,))  # lointain, pile au spot
        )
        choisi = self._choisir(contrats)
        self.assertIn("C00500000", choisi,
                      "un strike plus éloigné du spot a été retenu parce que "
                      "son échéance était plus proche")

    def test_a_strike_egal_l_echeance_la_plus_proche_gagne(self):
        """Le sens du départage est une décision de stratégie, écrite dans
        alpaca_cli.py et verrouillée ici : à égalité de strike, l'échéance la
        plus proche. Si quelqu'un décide l'inverse, ce test doit tomber et
        forcer la discussion, pas laisser le changement passer inaperçu."""
        choisi = self._choisir(self._contrats(list(reversed(self.ECHEANCES))))
        self.assertIn("260902", choisi)

    def test_aucun_contrat_rend_None(self):
        self.assertIsNone(self._choisir([]))



    # ------------------------------------------------------------------
    # Ajoutés le 27/08 : la troncature de page, que la bande ±5% a réduite
    # sans la fermer.
    # ------------------------------------------------------------------

    # Noms distincts de bout en bout : la classe definit deja SPOT,
    # _contrats() et surtout _choisir(). Mes helpers l'ecrasaient, donc
    # SES tests s'executaient avec MON spot -- deux rouges qui n'avaient
    # rien a voir avec le code de production.
    SPOT_TRONQUE = 762.98

    def _page_api(self, nb, depart=None, echeances=6, pas=1.0):
        """Une réponse d'API triée par strike CROISSANT, comme la vraie."""
        strike = depart if depart is not None else round(self.SPOT_TRONQUE * 0.95, 2)
        page = []
        for i in range(nb):
            page.append({"symbol": "SPY2609%02dC%08d" % (2 + i % echeances,
                                                          int(strike * 1000)),
                         "strike_price": "%.2f" % strike,
                         "expiration_date": "2026-09-%02d" % (2 + i % echeances)})
            if i % echeances == echeances - 1:
                strike += pas
        return page

    def _choisir_sur_page(self, page):
        from unittest import mock
        with mock.patch.object(alpaca_cli, "run",
                               lambda a: {"option_contracts": page}):
            return alpaca_cli.find_near_the_money_contract("SPY", +1,
                                                           spot=self.SPOT_TRONQUE)

    def test_une_page_tronquee_avant_le_spot_ne_rend_pas_un_contrat_au_hasard(self):
        """L'API pagine à 100 résultats triés par strike CROISSANT. Le
        correctif du 24/08 a borné les strikes à ±5% du spot, ce qui suffit
        quand les strikes sont espacés de 5 $ — mais pas au dollar :

            bande ±5% sur SPY à 762.98 = 76 points
            76 strikes x 6 échéances (lun/mer/ven sur 7-21 j) = 462 contrats
            tronqué à 100 -> la page s'arrête à ~740, le spot n'y est PAS

        Mesuré sur une page ainsi construite : la fonction rendait un contrat
        22 points DANS LA MONNAIE (~2215 $ d'intrinsèque) comme un choix
        « at the money », sans un mot.

        PORTÉE HONNÊTE : je n'ai pas pu vérifier contre l'API réelle si SPY
        a effectivement des strikes au dollar et six échéances dans cette
        fenêtre — le commentaire du 24/08 dit la correction vérifiée en
        conditions réelles. Ce test ne prouve donc pas que le cas est actif ;
        il prouve qu'AUCUNE détection n'existait s'il l'était, pour une panne
        que ce projet a déjà subie une fois."""
        page = self._page_api(100)
        strikes = [float(c["strike_price"]) for c in page]
        self.assertLess(max(strikes), self.SPOT_TRONQUE, "prérequis : spot hors page")
        self.assertIsNone(
            self._choisir_sur_page(page),
            "une page tronquée AVANT le spot rend quand même un contrat, "
            "présenté comme le plus proche de la monnaie")

    def test_une_page_pleine_qui_encadre_le_spot_reste_exploitable(self):
        """Témoin indispensable : refuser dès que la page est pleine
        interdirait de trader les sous-jacents les plus liquides. Si le spot
        est DANS l'intervalle rendu, le plus proche y est aussi — le tri par
        strike le garantit."""
        page = self._page_api(100, depart=self.SPOT_TRONQUE - 8, echeances=2, pas=0.5)
        strikes = [float(c["strike_price"]) for c in page]
        self.assertLess(min(strikes), self.SPOT_TRONQUE)
        self.assertGreater(max(strikes), self.SPOT_TRONQUE)
        self.assertIsNotNone(self._choisir_sur_page(page),
                             "une page pleine encadrant le spot est refusée à tort")

    def test_une_page_courte_sans_le_spot_reste_exploitable(self):
        """L'autre moitié du témoin, et elle compte autant : une page COURTE
        n'a pas été tronquée. Si aucun strike n'atteint le spot, c'est le
        marché qui est ainsi, pas la pagination — et le plus proche est
        vraiment le plus proche. Refuser ici confondrait « je n'ai pas tout
        vu » avec « il n'y a rien de mieux »."""
        page = self._page_api(12)
        self.assertIsNotNone(self._choisir_sur_page(page),
                             "une page non tronquée est refusée à tort")

class TestBasculeDeCompte(BaseExit):
    """Passer de `.env` du compte de dev au compte dédié du hackathon est une
    étape PRÉVUE. state.json est un fichier unique sans conscience du compte :
    sans remise à zéro, la comptabilité de l'ancien compte s'appliquerait au
    nouveau.

    _record_starting_equity() gère ce cas depuis le 24/08, et son propre
    docstring raconte comment deux champs ajoutés plus tard (traded_today,
    consecutive_losses) avaient été oubliés dans la liste. Le 27/08,
    exits_counted a été ajouté et oublié à son tour — la fonction avait prédit
    sa propre rechute. Aucun test ne couvrait cette bascule.
    """

    ANCIEN = "compte-de-dev"
    NOUVEAU = "compte-hackathon"

    def _etat_sale(self):
        """Un état plausible de fin de semaine sur l'ANCIEN compte."""
        return {
            "account_id": self.ANCIEN,
            "starting_equity": 50000.0,
            "locked": True,
            "lock_reason": "verrou de perte hebdomadaire",
            "traded_today": {"date": risk_gates._today(), "symbols": ["SPY", "QQQ"]},
            "consecutive_losses": 3,
            "exits_counted": {"SPY260831C00500000": "loss"},
        }

    def test_la_bascule_efface_toute_la_comptabilite_de_l_ancien_compte(self):
        etat = risk_gates._record_starting_equity(
            120000.0, self._etat_sale(), self.NOUVEAU)
        self.assertEqual(etat["account_id"], self.NOUVEAU)
        self.assertEqual(etat["starting_equity"], 120000.0)
        self.assertFalse(etat["locked"],
                         "un verrou de l'ancien compte survit sur le nouveau")
        self.assertEqual(etat["consecutive_losses"], 0,
                         "une série de pertes de l'ancien compte pourrait faire "
                         "sauter le disjoncteur sur un compte qui n'a jamais tradé")
        self.assertEqual(etat["traded_today"]["symbols"], [],
                         "un symbole tradé sur l'ancien compte paraît déjà "
                         "tradé sur le nouveau")
        self.assertEqual(etat["exits_counted"], {},
                         "une sortie comptée sur l'ancien compte pourrait faire "
                         "prendre une vraie perte du nouveau pour un doublon")

    def test_l_etat_apres_bascule_de_compte_est_epingle(self):
        """LE GARDE MÉCANIQUE. Deux champs ont déjà été oubliés dans la liste
        de remise à zéro, à deux dates différentes, chacun ajouté après coup.
        Un test par champ ne suffit pas : il faut que le PROCHAIN champ ajouté
        fasse tomber quelque chose.

        Ce test épingle l'état ENTIER. Ajouter un champ à state.json sans
        décider ce qu'il devient à la bascule fera tomber ce test — ce qui
        force la décision au lieu de la laisser passer une troisième fois."""
        etat = risk_gates._record_starting_equity(
            120000.0, self._etat_sale(), self.NOUVEAU)
        self.assertEqual(
            etat,
            {
                "account_id": self.NOUVEAU,
                "starting_equity": 120000.0,
                "locked": False,
                "lock_reason": None,
                "traded_today": {"date": risk_gates._today(), "symbols": []},
                "consecutive_losses": 0,
                "exits_counted": {},
            },
            "l'état après bascule ne correspond plus à ce qui est épinglé : un "
            "champ a été ajouté à state.json sans décider ce qu'il devient "
            "quand on change de compte")

    def test_un_premier_passage_ne_detruit_pas_la_memoire_des_sorties(self):
        """La nuance que la SUITE a trouvée, pas la relecture.

        manage_exits() écrit exits_counted juste avant d'appeler
        _record_exit_outcome(), qui atterrit dans _record_starting_equity(). Sur
        un état où starting_equity n'est pas encore posé — le cas normal d'une
        machine où seul monitor_exits.py a tourné, puisqu'il n'appelle jamais
        check_gates — effacer ici détruit ce qui vient d'être inscrit dans la
        MÊME itération, et la position bloquée est recomptée au passage suivant.

        Une remise à zéro n'a de sens que sur une VRAIE bascule de compte."""
        etat = {"exits_counted": {"SPY260831C00500000": "loss"}}   # pas de starting_equity
        rendu = risk_gates._record_starting_equity(100000.0, etat, "compte-neuf")
        self.assertEqual(rendu["starting_equity"], 100000.0,
                         "prérequis : la référence doit bien être posée")
        self.assertEqual(rendu["exits_counted"], {"SPY260831C00500000": "loss"},
                         "la mémoire des sorties déjà comptées a été détruite "
                         "par un simple premier passage : la position bloquée "
                         "sera recomptée au cycle suivant")

    def test_le_meme_compte_ne_declenche_aucune_remise_a_zero(self):
        """Contrôle : sans lui, tout remettre à zéro à CHAQUE appel passerait
        les deux tests ci-dessus — et effacerait le verrou de perte à chaque
        exécution."""
        etat = self._etat_sale()
        etat["account_id"] = self.NOUVEAU
        rendu = risk_gates._record_starting_equity(999999.0, etat, self.NOUVEAU)
        self.assertTrue(rendu["locked"],
                        "le verrou de perte est effacé alors que le compte n'a "
                        "pas changé")
        self.assertEqual(rendu["starting_equity"], 50000.0,
                         "la référence est ré-établie alors que le compte n'a "
                         "pas changé : le drawdown repartirait de zéro à chaque "
                         "exécution et le verrou ne se déclencherait jamais")
        self.assertEqual(rendu["consecutive_losses"], 3)


class TestCoupeCircuit(unittest.TestCase):
    """Le fichier HALT est la seule façon pour un humain d'arrêter l'agent sans
    toucher au code ni aux identifiants. Son docstring dit que tout son intérêt
    est de fonctionner « même si tout le reste de l'environnement est dégradé ».

    Il utilisait Path.exists(), qui SUIT les liens symboliques. Mesuré le
    27/08 : un lien symbolique cassé nommé HALT donnait (False, '') — l'agent
    continuait d'ouvrir des positions alors qu'un fichier nommé HALT était posé
    là, créé par un humain.

    Pour un coupe-circuit, la bonne question n'est pas « la cible est-elle
    lisible » mais « CE NOM EST-IL LÀ ». Et ne pas pouvoir le déterminer doit
    se lire comme un arrêt : c'est la seule direction sûre, et elle ne bloque
    que les ENTRÉES, jamais les sorties.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="hindsight-halt-"))
        self._vrai = risk_gates.HALT_FILE

    def tearDown(self):
        risk_gates.HALT_FILE = self._vrai
        for chemin in self.tmp.rglob("*"):
            if chemin.is_dir():
                try:
                    os.chmod(chemin, 0o755)
                except OSError:
                    pass
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _halt(self, chemin):
        risk_gates.HALT_FILE = chemin
        return risk_gates.is_halted()

    def test_un_lien_symbolique_casse_arrete_quand_meme_l_agent(self):
        """Le témoin : avant correctif, (False, '')."""
        h = self.tmp / "HALT"
        h.symlink_to(self.tmp / "cible_qui_n_existe_pas")
        arrete, raison = self._halt(h)
        self.assertTrue(arrete,
                        "un fichier nommé HALT est posé là et l'agent continue "
                        "d'ouvrir des positions")
        self.assertIn("unreadable", raison)

    def test_un_repertoire_illisible_compte_comme_une_pause(self):
        sd = self.tmp / "verrou"
        sd.mkdir()
        (sd / "HALT").write_text("pause", encoding="utf-8")
        os.chmod(sd, 0o000)
        try:
            if os.access(sd, os.R_OK):
                self.skipTest("les permissions ne bloquent pas ici (root ?)")
            arrete, raison = self._halt(sd / "HALT")
        finally:
            os.chmod(sd, 0o755)
        self.assertTrue(arrete,
                        "le coupe-circuit ne peut pas être lu et l'agent se "
                        "considère libre de trader")
        self.assertIn("could not be checked", raison)

    def test_la_raison_ecrite_par_l_operateur_est_rendue(self):
        h = self.tmp / "HALT"
        h.write_text("  pause demandée à 2h du matin  ", encoding="utf-8")
        self.assertEqual(self._halt(h), (True, "pause demandée à 2h du matin"))

    def test_un_fichier_vide_arrete_avec_une_raison_par_defaut(self):
        h = self.tmp / "HALT"
        h.write_text("", encoding="utf-8")
        arrete, raison = self._halt(h)
        self.assertTrue(arrete)
        self.assertIn("no reason given", raison)

    def test_l_absence_reelle_ne_declenche_rien(self):
        """Contrôle : sans lui, « tout compte comme une pause » passerait les
        quatre tests ci-dessus et l'agent ne traderait plus jamais."""
        self.assertEqual(self._halt(self.tmp / "jamais_cree"), (False, ""))


class TestCoherenceDesTables(unittest.TestCase):
    """Deux tables doivent rester d'accord, et rien ne le vérifiait."""

    def test_chaque_symbole_de_l_univers_a_un_secteur(self):
        """sector_of() retombe sur le symbole LUI-MÊME pour un inconnu. Chaque
        symbole hors table devient donc son propre secteur, et le plafond
        sectoriel se dégrade en silence vers la simple règle « un seul par
        sous-jacent ».

        Le README annonce pourtant que ce plafond « stops being a no-op the
        moment the universe grows past one symbol per sector ». Ajouter un
        symbole sans l'inscrire dans SECTOR_MAP le laisserait no-op, sans un
        mot. L'univers actuel est couvert ; ce test garantit qu'il le reste."""
        import agent
        manquants = [s for s in agent.DEFAULT_UNIVERSE
                     if s.upper() not in risk_gates.SECTOR_MAP]
        self.assertEqual(manquants, [],
                         "symbole(s) de DEFAULT_UNIVERSE absent(s) de "
                         "SECTOR_MAP : %s — le plafond sectoriel ne s'applique "
                         "pas à eux" % ", ".join(manquants))

    def test_sector_of_est_insensible_a_la_casse(self):
        self.assertEqual(risk_gates.sector_of("spy"), risk_gates.sector_of("SPY"))

    def test_un_symbole_inconnu_ne_partage_le_secteur_de_personne(self):
        """Le repli est délibéré : un symbole inconnu ne doit pas être rangé
        dans un mauvais secteur. Ce test fige ce choix plutôt que de le laisser
        implicite."""
        a = risk_gates.sector_of("ZZZZ")
        self.assertEqual(a, "ZZZZ")
        self.assertNotIn(a, set(risk_gates.SECTOR_MAP.values()))


if __name__ == "__main__":
    unittest.main(verbosity=2)
