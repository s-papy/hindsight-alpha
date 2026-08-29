# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha
#
# Sous licence MIT, redistribuer ce fichier -- entier ou par morceaux --
# OBLIGE a conserver cet avis. C'est la seule contrainte de la licence, et
# c'est la raison d'etre de ces trois lignes : un fichier copie-colle
# emporte desormais sa provenance avec lui.

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
from datetime import datetime, timedelta, timezone
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
            # Voir la note de BaseExit dans test_risk_gates.py : cette
            # suite lisait le `.env` de la machine, et 61 tests sont
            # devenus rouges a la seconde ou ALPACA_ACCOUNT_ID a ete
            # declare pour de vrai, sans qu'une ligne de code ait bouge.
            "ACCOUNT_ID": config.ACCOUNT_ID,
        }
        config.ACCOUNT_ID = None
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
        config.ACCOUNT_ID = self._sauve["ACCOUNT_ID"]
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


class TestLAgentNOMME_ce_qu_il_ecrit(BaseAgent):
    """monitor_exits.py marquait ses entrées `run_type: "exit_monitor"`
    depuis toujours. L'agent n'écrivait AUCUN marqueur : le tableau de bord
    devait donc le reconnaître à l'ABSENCE de type.

    Posé le 28/08/2026 au soir, une fois le premier passage live terminé —
    le suivant n'étant que lundi, la fenêtre était sûre. On ne touche pas au
    chemin de trading une demi-heure avant qu'il serve."""

    def test_chaque_passage_est_marque_comme_agent(self):
        # On passe par main(), PAS par le helper _lance : celui-ci construit
        # son propre dictionnaire et court-circuite l'endroit meme ou le
        # marqueur est pose. Ma premiere version testait donc le harnais, pas
        # le code -- elle est tombee, et elle avait raison de tomber.
        argv = sys.argv
        sys.argv = ["agent.py", "--symbols", "SPY"]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                try:
                    agent.main()
                except SystemExit:
                    pass
        finally:
            sys.argv = argv
        lignes = [l for l in decision_log.LOG_FILE.read_text(
            encoding="utf-8").splitlines() if l.strip()]
        self.assertTrue(lignes, "aucune entree de journal ecrite")
        record = json.loads(lignes[-1])
        self.assertEqual(
            record.get("run_type"), "agent",
            "un passage de l'agent n'est pas nommé : le tableau de bord doit "
            "alors le deviner, et devinera mal le jour où un troisième type "
            "d'entrée apparaîtra")


class TestLaMargeEstECRITEDansLeJournal(BaseAgent):
    """Mesurer sans écrire ne servirait à rien : la marge doit être
    VÉRIFIABLE APRÈS COUP, dans l'enregistrement du passage.

    L'horloge factice de BaseAgent ne porte pas de `next_close` — c'est
    d'ailleurs ce qui a prouvé, sur les 480 tests, que l'ajout ne lève pas
    quand le champ manque. Ici on le fournit."""

    def test_la_marge_et_la_cloche_sont_enregistrees(self):
        cloche = (datetime.now(timezone.utc) + timedelta(minutes=23)).isoformat()
        alpaca_cli.get_clock = lambda: {"is_open": True, "next_close": cloche}
        record = self._lance(["SPY"])
        self.assertEqual(record.get("next_close"), cloche)
        self.assertIsNotNone(record.get("minutes_before_close"),
                             "la marge avant la cloche n'est pas enregistrée : "
                             "elle ne pourra pas être vérifiée après coup")
        self.assertEqual(record["minutes_before_close"], 22)

    def test_une_cloche_ABSENTE_ne_fait_pas_tomber_le_passage(self):
        """TÉMOIN : l'API peut ne pas renvoyer le champ. Le passage doit
        continuer — mesurer la marge n'est pas une condition pour trader, et
        transformer une information manquante en panne serait pire que le
        défaut d'origine."""
        alpaca_cli.get_clock = lambda: {"is_open": True}
        record = self._lance(["SPY"])
        self.assertIsNone(record.get("minutes_before_close"))
        self.assertNotEqual(record.get("outcome"), "unknown",
                            "le passage ne s'est pas déroulé")


class TestLaMargeAvantLaCloche(unittest.TestCase):
    """L'agent est planifié à 21:37 CEST — 15:37 à New York, soit VINGT-TROIS
    minutes avant la cloche.

    L'horloge du marché n'était lue qu'UNE fois, au démarrage, et
    `next_close` — pourtant documenté dans `alpaca_cli.get_clock` — n'était
    lu NULLE PART dans le dépôt. Un ordre parti après la cloche est le plus
    souvent rejeté, et ce cas dégrade proprement (ECHECS_TERMINAUX). Mais un
    ordre simplement MIS EN FILE pour la séance suivante remonterait
    « accepted » : la position s'ouvrirait au prix d'ouverture du lendemain,
    pas à celui que la décision a examiné, et rien ne le dirait.

    Aucun refus n'a été ajouté — ce serait un garde de risque, et aucun seuil
    de ce dépôt ne bouge sans décision humaine. On MESURE, et la marge est
    écrite dans le journal de décision.
    """

    def test_une_marge_lisible_est_rendue_en_minutes(self):
        futur = (datetime.now(timezone.utc) + timedelta(minutes=45)).isoformat()
        self.assertEqual(agent._minutes_avant(futur), 44)

    def test_le_suffixe_Z_est_compris(self):
        """Alpaca écrit ses horodatages avec un Z, pas un +00:00."""
        futur = (datetime.now(timezone.utc)
                 + timedelta(minutes=90)).isoformat().replace("+00:00", "Z")
        self.assertEqual(agent._minutes_avant(futur), 89)

    def test_une_marge_ILLISIBLE_rend_None_et_JAMAIS_zero(self):
        """Le point qui compte, et c'est le motif de tout ce dépôt.

        Zéro se lirait « il ne reste plus une minute » — une mesure, et une
        alarmante. None se lit « je ne sais pas », et le champ manque alors
        dans le journal, ce qui se voit. « Je n'ai pas compris » n'est pas
        « il n'y a rien »."""
        for valeur in (None, "", "pas une date", 12345, [], {}):
            with self.subTest(valeur=valeur):
                self.assertIsNone(
                    agent._minutes_avant(valeur),
                    "une marge illisible (%r) est rendue comme un nombre : "
                    "elle sera lue comme une mesure" % (valeur,))

    def test_une_cloche_DEJA_passee_rend_un_negatif_pas_None(self):
        """TÉMOIN. Sans lui, une fonction qui rendrait None à tout coup
        passerait le test ci-dessus — et la marge ne serait jamais mesurée.

        Un négatif est une information réelle : la cloche est passée. Le
        confondre avec « illisible » effacerait précisément le cas qu'on
        cherche à voir."""
        passe = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        marge = agent._minutes_avant(passe)
        self.assertIsNotNone(marge, "une cloche déjà passée est traitée comme "
                                    "illisible : le cas dangereux disparaît")
        self.assertLess(marge, 0)


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

    def test_la_publication_automatique_decidee_est_toujours_en_place(self):
        """CE TEST DISAIT L'INVERSE le matin du 27/08 : il exigeait qu'AUCUN
        agent ne passe --git-push, au nom de la docstring de
        publish_dashboard.py.

        Il encodait ma décision, pas celle de l'auteur. Le README documente EN
        GRAS l'automatisation comme « a deliberate change to a rule this project
        used to hold » — la page est l'URL de soumission, une règle qui la
        laisse périmée protégeait la mauvaise chose — et cette docstring est
        précisément celle que ce paragraphe déclare périmée. Spap a confirmé :
        remettre.

        L'invariant correct n'est pas « aucun push automatique », c'est « le
        plist et le README disent la même chose ». controle_readme_decrit_les_agents()
        le vérifie en général ; ce test épingle le cas décidé, pour que le
        retirer à nouveau fasse tomber quelque chose au lieu de passer."""
        publication = [f for f in self._plists() if "publish-dashboard" in f.name]
        if not publication:
            self.skipTest("pas de plist de publication")
        actives = []
        for f in publication:
            for ligne in f.read_text(encoding="utf-8").splitlines():
                nu = ligne.strip()
                if nu.startswith("<!--") or nu.startswith("--"):
                    continue      # une mention en commentaire n'est pas active
                if nu == "<string>--git-push</string>":
                    actives.append(f.name)
        self.assertTrue(actives,
                        "--git-push a été retiré du plist de publication. Le "
                        "README documente cette automatisation comme une "
                        "décision délibérée : si elle est révoquée, c'est le "
                        "README qu'il faut amender d'abord.")

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


class TestLeChiffreDeTestsAnnonceEstMESURE(unittest.TestCase):
    """Un chiffre public qui ne tient plus est une fausse mesure.

    Le README annonçait « 12 offline regression tests » — et, plus loin,
    « 206 offline tests ». Mesure du 28/08/2026 : 495. Deux chiffres
    périmés DIFFÉRENTS dans le même document : la dérive s'était donc
    produite plus d'une fois. Et il ne s'agissait pas d'une exagération
    mais de l'inverse — le README sous-estimait le travail d'un facteur 40,
    sur la ligne « Proof it runs » qu'un jury lit en premier.

    `controle_chiffres_perimes()` existait déjà, mais c'est une LISTE NOIRE
    de valeurs connues : il ne peut attraper « 12 » que si quelqu'un pense à
    l'y inscrire — c'est-à-dire au moment précis où il ne l'a pas fait.

    Le contrôle ajouté ici MESURE LES DEUX CÔTÉS, donc il ne peut pas
    devenir périmé à son tour. Ce test le vérifie en cassant le README pour
    de bon, comme TestGardeFouMordVraiment le fait pour le garde
    live-trading."""

    RACINE = Path(__file__).resolve().parent

    def _lancer_avec_readme(self, contenu_readme):
        d = Path(tempfile.mkdtemp(prefix="hindsight-chiffres-"))
        try:
            for nom in ("garde_fou.py", "config.py"):
                shutil.copy(self.RACINE / nom, d / nom)
            # trois tests reels, comptes par l'arbre syntaxique
            (d / "test_faux.py").write_text(
                "import unittest\n"
                "class T(unittest.TestCase):\n"
                "    def test_a(self): pass\n"
                "    def test_b(self): pass\n"
                "    def test_c(self): pass\n", encoding="utf-8")
            (d / "README.md").write_text(contenu_readme, encoding="utf-8")
            r = subprocess.run([sys.executable, str(d / "garde_fou.py")],
                               cwd=str(d), capture_output=True, text=True,
                               timeout=120)
            return r.stdout + r.stderr
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_un_chiffre_FAUX_est_signale(self):
        sortie = self._lancer_avec_readme(
            "# Projet\n\nCovered by 12 offline regression tests.\n")
        self.assertIn(
            "alors que le depot en contient 3", sortie,
            "le garde-fou laisse passer un chiffre de tests faux — un jury "
            "le lit pourtant comme une mesure :\n%s" % sortie[-600:])

    def test_le_BON_chiffre_ne_declenche_RIEN(self):
        """TÉMOIN, et c'est lui qui compte : sans lui, un contrôle qui
        alerterait sur TOUT chiffre passerait le test ci-dessus, et le
        README ne pourrait plus jamais citer un nombre de tests."""
        sortie = self._lancer_avec_readme(
            "# Projet\n\nCovered by 3 offline regression tests.\n")
        self.assertNotIn(
            "alors que le depot en contient", sortie,
            "un chiffre EXACT est signalé comme périmé :\n%s" % sortie[-600:])

    def test_un_minorant_explicite_reste_vrai(self):
        """« 3+ tests » avec 3 tests reels : VRAI, donc aucune alerte.

        Ajoute dans la foulee du controle lui-meme : la version stricte a
        signale TROIS FOIS de suite un README que je venais de corriger,
        parce que chaque test ajoute changeait le total. Exiger un chiffre
        exact dans un document, c'est le condamner a etre faux entre deux
        commits — et pousser l'auteur a desarmer le controle."""
        # « 2+ » et NON « 3+ » : avec 3 tests reels, « 3+ » passerait aussi
        # bien si le signe + etait ignore (3 == 3), donc ce test ne
        # distinguerait RIEN. Trouve par mutation : neutraliser la branche du
        # minorant ne faisait tomber aucun test. Un minorant STRICT, lui,
        # echoue des que le + n'est plus honore.
        sortie = self._lancer_avec_readme(
            "# Projet\n\nCovered by 2+ offline regression tests.\n")
        self.assertNotIn("alors que le depot en contient", sortie,
                         "« 2+ tests » avec 3 tests reels est VRAI, et pourtant "
                         "signale :\n%s" % sortie[-400:])

    def test_un_minorant_FAUX_est_quand_meme_signale(self):
        """TEMOIN. Sans lui, il suffirait d'ecrire « 9000+ » pour que
        n'importe quelle affirmation passe. Un minorant reste une
        affirmation : elle doit etre vraie."""
        sortie = self._lancer_avec_readme(
            "# Projet\n\nCovered by 9000+ offline regression tests.\n")
        self.assertIn(
            "alors que le depot en contient 3", sortie,
            "« 9000+ tests » passe alors qu'il y en a 3 : le signe + sert "
            "d'echappatoire a toute verification.\n%s" % sortie[-500:])

    def test_un_chiffre_NU_doit_rester_EXACT(self):
        """TEMOIN : on relache sur l'approximation ASSUMEE, jamais sur
        l'affirmation precise. « 4 tests » quand il y en a 3 reste faux."""
        sortie = self._lancer_avec_readme(
            "# Projet\n\nCovered by 4 offline regression tests.\n")
        self.assertIn("alors que le depot en contient 3", sortie)

    def test_un_README_SANS_chiffre_ne_declenche_RIEN(self):
        """Ne rien annoncer n'est pas une faute — c'est annoncer FAUX qui
        l'est."""
        sortie = self._lancer_avec_readme("# Projet\n\nAucun chiffre ici.\n")
        self.assertNotIn("alors que le depot en contient", sortie)


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
class TestLeHookRefuseUnCodeNonTESTE(unittest.TestCase):
    """Rien n'empêchait mécaniquement de committer sur une suite rouge.

    Le hook de pre-commit ne lançait que garde_fou.py. J'ai committé QUATRE
    FOIS le 28/08/2026 sur une suite rouge sans m'en apercevoir — la
    dernière en ajoutant un contrôle censé empêcher exactement ce genre de
    dérive. Une règle qu'on se rappelle ne vaut rien face à une règle que
    l'outil applique.

    Ces tests exercent le VRAI hook dans un dépôt jetable, avec une suite
    minuscule : c'est la vérité-terrain, pas une lecture du script.

    Les deux témoins comptent autant que le cas rouge :
      . une suite VERTE doit passer — sinon plus aucun commit n'est possible ;
      . un commit qui ne touche PAS de .py ne doit rien lancer — le tableau
        de bord commite tout seul toutes les 30 minutes et ne touche que
        docs/data.json ; lui faire payer 70 s serait absurde.
    """

    RACINE = Path(__file__).resolve().parent
    SUITE_VERTE = ("import unittest\n"
                   "class T(unittest.TestCase):\n"
                   "    def test_ok(self): pass\n")
    SUITE_ROUGE = ("import unittest\n"
                   "class T(unittest.TestCase):\n"
                   "    def test_casse(self): self.assertEqual(1, 2)\n")

    def _depot(self):
        d = Path(tempfile.mkdtemp(prefix="hindsight-hook-tests-"))
        shutil.copytree(self.RACINE / "githooks", d / "githooks")
        (d / "githooks" / "pre-commit").chmod(0o755)
        # garde_fou factice qui approuve : ce qu'on teste ici est la SUITE,
        # pas le garde-fou, et le vrai exigerait tout le dossier.
        (d / "garde_fou.py").write_text("import sys\nsys.exit(0)\n",
                                        encoding="utf-8")
        (d / "docs").mkdir()
        (d / "docs" / "data.json").write_text("{}", encoding="utf-8")
        for a in (["init", "-q", "."], ["config", "user.email", "t@t"],
                  ["config", "user.name", "t"],
                  ["config", "core.hooksPath", "githooks"]):
            subprocess.run([GIT, *a], cwd=str(d), check=True,
                           capture_output=True, timeout=30)
        return d

    def _commiter(self, d, message):
        subprocess.run([GIT, "add", "-A"], cwd=str(d), check=True,
                       capture_output=True, timeout=30)
        r = subprocess.run([GIT, "commit", "-m", message], cwd=str(d),
                           capture_output=True, text=True, timeout=300)
        return r.returncode, r.stdout + r.stderr

    def test_du_code_avec_une_suite_ROUGE_est_refuse(self):
        d = self._depot()
        try:
            (d / "test_x.py").write_text(self.SUITE_VERTE, encoding="utf-8")
            self.assertEqual(self._commiter(d, "base")[0], 0, "le commit de base a échoué")
            (d / "test_y.py").write_text(self.SUITE_ROUGE, encoding="utf-8")
            code, sortie = self._commiter(d, "code casse")
            self.assertNotEqual(code, 0,
                                "un commit sur une suite ROUGE est passé :\n%s" % sortie)
            self.assertIn("ROUGE", sortie)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_du_code_avec_une_suite_VERTE_passe(self):
        """TÉMOIN : sans lui, un hook qui refuserait TOUT passerait le test
        ci-dessus, et plus aucun commit ne serait possible."""
        d = self._depot()
        try:
            (d / "test_x.py").write_text(self.SUITE_VERTE, encoding="utf-8")
            code, sortie = self._commiter(d, "code vert")
            self.assertEqual(code, 0, "un commit parfaitement vert est refusé :\n%s" % sortie)
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_un_commit_SANS_python_ne_lance_pas_la_suite(self):
        """TÉMOIN : le tableau de bord commite tout seul toutes les 30 min et
        ne touche que docs/data.json. Lui faire payer la suite serait absurde
        — et me pousserait à désarmer le hook."""
        d = self._depot()
        try:
            (d / "test_x.py").write_text(self.SUITE_VERTE, encoding="utf-8")
            self._commiter(d, "base")
            (d / "docs" / "data.json").write_text('{"x": 1}', encoding="utf-8")
            code, sortie = self._commiter(d, "snapshot")
            self.assertEqual(code, 0)
            self.assertNotIn("lancement de la suite", sortie,
                             "la suite tourne pour un commit sans code Python")
        finally:
            shutil.rmtree(d, ignore_errors=True)


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


class TestInventaireDesControles(unittest.TestCase):
    """Le nombre de contrôles est affiché à chaque run de garde_fou.py. Il
    était recopié à la main et a PÉRIMÉ DEUX FOIS — le commentaire du script
    admettait lui-même qu'il « trainait encore à 4 » après le passage à 6, et
    qu'il avait fallu une revue croisée pour le voir. Il est désormais dérivé
    de la liste CONTROLES.

    Reste le risque que la dérivation ne couvre pas : un contrôle DÉFINI dans
    le fichier et jamais ajouté à la liste. Le compte affiché serait alors
    juste, et le contrôle ne tournerait jamais.
    """

    RACINE = Path(__file__).resolve().parent

    def test_tout_controle_defini_est_appele(self):
        source = (self.RACINE / "garde_fou.py").read_text(encoding="utf-8")
        definis = set(re.findall(r"^def (controle_\w+)\(", source, re.M))
        self.assertTrue(definis, "aucune fonction controle_* trouvée")
        bloc = re.search(r"CONTROLES = \(([^)]*)\)", source, re.S)
        self.assertIsNotNone(bloc, "la liste CONTROLES a disparu de garde_fou.py")
        listes = set(re.findall(r"(controle_\w+)", bloc.group(1)))
        oublies = sorted(definis - listes)
        self.assertEqual(oublies, [],
                         "contrôle(s) défini(s) mais jamais appelé(s) : %s — le "
                         "compte affiché resterait juste et le contrôle ne "
                         "tournerait jamais" % ", ".join(oublies))

    def test_le_nombre_affiche_correspond_aux_controles_reels(self):
        source = (self.RACINE / "garde_fou.py").read_text(encoding="utf-8")
        definis = re.findall(r"^def (controle_\w+)\(", source, re.M)
        proc = subprocess.run([sys.executable, "garde_fou.py"],
                              cwd=str(self.RACINE), capture_output=True,
                              text=True, timeout=120)
        m = re.search(r"attrape (\d+) formes d'erreur", proc.stdout)
        self.assertIsNotNone(m, "le script n'annonce plus son nombre de contrôles")
        self.assertEqual(int(m.group(1)), len(definis),
                         "le script annonce %s contrôles, il en définit %d"
                         % (m.group(1), len(definis)))



class TestRunInterrompu(unittest.TestCase):
    """Ajouté le 27/08. `record` naît avec `outcome: "unknown"` — le sens
    littéral de « on ne sait pas ce qui s'est passé ». Les deux `except` de
    main() rattrapent SystemExit et Exception ; KeyboardInterrupt n'est ni
    l'un ni l'autre (BaseException), donc le `finally` s'exécutait en
    laissant ce défaut en place.

    Ce qui rend le cas grave plutôt que théorique : monitor_last_run.json est
    réécrit avec un horodatage FRAIS, et la fraîcheur est précisément le
    signal que la bannière de santé publique surveille. Mesuré : moniteur
    programmé réellement mort (4 échecs consécutifs), bannière ROUGE ; un
    Ctrl-C sur un lancement manuel, et la même bannière passe au VERT
    « healthy » sans que rien n'ait été réparé.

    Corrigé des deux côtés — voir aussi test_dashboard.TestBanniereDeSante
    pour la moitié JavaScript. Ici : le moniteur doit NOMMER l'interruption."""

    CONCLUANTS = ("checked", "market_closed")

    def setUp(self):
        import config, decision_log, monitor_exits, risk_gates
        self.mods = (config, decision_log, monitor_exits, risk_gates)
        self.tmp = Path(tempfile.mkdtemp(prefix="hindsight-interrompu-"))
        self.sauve = (monitor_exits.MONITOR_STATUS_FILE, monitor_exits.DEDUP_FILE,
                      decision_log.LOG_FILE, config.require_credentials,
                      risk_gates.manage_exits, sys.argv)
        monitor_exits.MONITOR_STATUS_FILE = self.tmp / "monitor_last_run.json"
        monitor_exits.DEDUP_FILE = self.tmp / "dedup.json"
        decision_log.LOG_FILE = self.tmp / "decision_log.jsonl"
        config.require_credentials = lambda: None
        sys.argv = ["monitor_exits.py", "--skip-market-check"]

    def tearDown(self):
        config, decision_log, monitor_exits, risk_gates = self.mods
        (monitor_exits.MONITOR_STATUS_FILE, monitor_exits.DEDUP_FILE,
         decision_log.LOG_FILE, config.require_credentials,
         risk_gates.manage_exits, sys.argv) = self.sauve
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_interrompu(self):
        _, _, monitor_exits, risk_gates = self.mods
        def ctrl_c(dry_run=False):
            raise KeyboardInterrupt()
        risk_gates.manage_exits = ctrl_c
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(KeyboardInterrupt):
                monitor_exits.main()
        return json.loads(monitor_exits.MONITOR_STATUS_FILE.read_text(
            encoding="utf-8"))

    def test_un_run_interrompu_ne_se_declare_pas_verifie(self):
        statut = self._run_interrompu()
        self.assertNotIn(statut.get("outcome"), self.CONCLUANTS,
                         "un run interrompu se présente comme une "
                         "vérification aboutie")
        self.assertNotEqual(
            statut.get("outcome"), "unknown",
            "l'interruption est enregistrée sous le défaut fourre-tout "
            "'unknown' : la bannière ne peut pas la distinguer d'un état "
            "qu'elle n'a jamais su nommer, et l'affichait en vert")
        self.assertEqual(statut.get("outcome"), "interrupted")

    def test_agent_py_nomme_aussi_son_interruption(self):
        """Le même défaut existait dans les DEUX points d'entrée — trouvé en
        croisant le vocabulaire d'`outcome` avec ce que la page sait rendre,
        pas en relisant agent.py. Là-bas la conséquence est moins grave (pas
        de bannière de santé à repeindre), mais un Ctrl-C au milieu d'une
        évaluation écrivait quand même une entrée publique qui ne dit rien :
        outcome 'unknown', error None."""
        import agent
        vrai_run = agent._run
        agent._run = lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt())
        sys.argv = ["agent.py", "--symbols", "SPY", "--dry-run"]
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(KeyboardInterrupt):
                    agent.main()
        finally:
            agent._run = vrai_run
        lignes = [l for l in self.mods[1].LOG_FILE.read_text(
            encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(json.loads(lignes[-1]).get("outcome"), "interrupted",
                         "un Ctrl-C sur agent.py est journalisé sous le "
                         "fourre-tout 'unknown'")

    def test_l_interruption_laisse_une_trace_durable(self):
        """Le fichier de statut est écrasé au run suivant. Si le seul endroit
        où l'interruption apparaît est ce fichier, elle disparaît quinze
        minutes plus tard sans que personne ne l'ait vue."""
        _, decision_log, _, _ = self.mods
        self._run_interrompu()
        self.assertTrue(decision_log.LOG_FILE.exists(),
                        "aucune entrée de journal pour un run interrompu")
        lignes = [l for l in decision_log.LOG_FILE.read_text(
            encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(json.loads(lignes[-1]).get("outcome"), "interrupted")

    def test_le_journal_ne_juge_plus_sur_la_seule_valeur_error(self):
        """`noteworthy = record["outcome"] == "error"` était la MÊME liste
        noire que celle de la bannière, au même endroit logique.

        Première version de ce test : provoquer une RuntimeError et vérifier
        qu'elle est journalisée. Elle l'était — mais elle l'était DÉJÀ avant
        le correctif, parce que `except Exception` la traduit en "error".
        Le test était vide et rien ne le montrait. C'est précisément pour
        pouvoir l'écrire honnêtement que la décision est devenue une fonction
        nommée : on lui passe une valeur INVENTÉE, que le code de production
        ne produit pas encore, et c'est le seul moyen de prouver que le
        défaut penche du bon côté pour l'avenir."""
        _, _, monitor_exits, _ = self.mods
        for invente in ("partial", "timeout", "unknown", "", None):
            with self.subTest(outcome=invente):
                self.assertTrue(
                    monitor_exits._merite_le_journal(invente, []),
                    "outcome=%r est classé sans intérêt et ne laisse aucune "
                    "trace durable" % (invente,))

    def test_les_passages_sains_restent_hors_du_journal(self):
        """Le pendant obligatoire. Une liste blanche trop étroite journalise
        tout, et ~26 non-événements par jour évincent en un jour et demi la
        décision quotidienne de agent.py du tableau de bord public — le bruit
        exact que ce filtre existe pour empêcher."""
        _, decision_log, monitor_exits, risk_gates = self.mods
        for sain in ("checked", "market_closed"):
            with self.subTest(outcome=sain):
                self.assertFalse(monitor_exits._merite_le_journal(sain, []),
                                 "un passage sain et routinier serait journalisé")

        # Et le chemin complet, pas seulement la fonction isolée.
        risk_gates.manage_exits = lambda dry_run=False: []
        with contextlib.redirect_stdout(io.StringIO()):
            monitor_exits.main()
        self.assertFalse(decision_log.LOG_FILE.exists(),
                         "un passage routinier écrit quand même dans le "
                         "journal public : le filtre anti-bruit ne filtre plus")



class TestLExemptionDesChiffresPerimes(unittest.TestCase):
    """PREMIER USAGE du champ `exemption` de `MOTIFS_PERIMES`, en place
    depuis le 25/08 et jamais exercé jusqu'ici — donc jamais vérifié.

    Le 29/08, le nombre d'équipes inscrites au hackathon est passé de 546
    (chiffre du deck, mesuré le 25/08) à ~975, vérifié à la main sur le
    tableau de bord live de lablab.ai. « 546 » entre donc dans la liste
    noire — mais le deck le cite maintenant comme repère historique :

        « 975 teams registered on 29 Aug, up from 546 four days earlier »

    Sans exemption, le contrôle bloquerait la phrase même qui corrige
    l'erreur. Avec une exemption trop large, il ne bloquerait plus rien.

    Un mécanisme qui existe sans avoir jamais été branché est exactement la
    forme d'échec que ce dépôt traque ailleurs. Ces trois tests le
    branchent."""

    RACINE = Path(__file__).resolve().parent

    def _lancer(self, texte_readme):
        d = Path(tempfile.mkdtemp(prefix="hindsight-exemption-"))
        try:
            for nom in ("garde_fou.py", "config.py"):
                shutil.copy(self.RACINE / nom, d / nom)
            (d / "README.md").write_text(texte_readme, encoding="utf-8")
            r = subprocess.run([sys.executable, str(d / "garde_fou.py")],
                               cwd=str(d), capture_output=True, text=True,
                               timeout=120)
            return r.stdout + r.stderr
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_le_chiffre_perime_seul_est_BLOQUE(self):
        sortie = self._lancer("# Projet\n\n546 teams registered so far.\n")
        self.assertIn("CHIFFRE PÉRIMÉ « 546 »", sortie,
                      "l'ancien nombre d'équipes passe comme chiffre "
                      "courant :\n%s" % sortie[-700:])

    def test_le_meme_chiffre_cite_comme_REPERE_passe(self):
        """Le cas réel du deck. Sans cette exemption, le contrôle
        interdirait de dire d'où l'on vient — et la seule façon de le
        satisfaire serait d'effacer l'historique du chiffre."""
        sortie = self._lancer(
            "# Projet\n\n975 teams registered on 29 Aug, up from 546 four "
            "days earlier.\n")
        self.assertNotIn("CHIFFRE PÉRIMÉ « 546 »", sortie,
                         "le repère historique est bloqué comme s'il était "
                         "le chiffre courant :\n%s" % sortie[-700:])

    def test_une_exemption_LOINTAINE_ne_couvre_pas(self):
        r"""TÉMOIN, et c'est lui qui compte : si « up from » traîne ailleurs
        dans la page, le chiffre reste bloqué — sinon un seul emploi de ces
        deux mots blanchirait tout le document.

        CE QUI BLOQUE ICI, PRÉCISÉMENT — vérifié par mutation plutôt que
        supposé : c'est l'ancre `\s*$` du motif d'exemption, qui exige
        « up from » JUSTE avant le nombre. La fenêtre de 40 caractères
        borne en plus jusqu'où le contrôle regarde en arrière. Ma première
        rédaction de ce texte attribuait le refus à la seule fenêtre ; en
        élargissant celle-ci au document entier, le cas reste bloqué — donc
        ce n'était pas elle qui le tenait."""
        sortie = self._lancer(
            "# Projet\n\nThe count is up from where it was, and there is a "
            "good deal of prose between that clause and the figure, so the "
            "window has long since closed by the time we reach 546 teams.\n")
        self.assertIn("CHIFFRE PÉRIMÉ « 546 »", sortie,
                      "une exemption située hors de la fenêtre de 40 "
                      "caractères blanchit quand même le chiffre :\n%s"
                      % sortie[-700:])



class TestLeMotifDesJUMELLESEstDetecteToutSeul(unittest.TestCase):
    """QUATRE FOIS DANS LA MEME JOURNEE, le 29/08/2026, le même motif trouvé
    à la main : une règle appliquée à une branche et pas à sa jumelle.

        bilan_semaine      gel illisible -> on s'arrête ; journal illisible
                           -> on accusait l'agent
        verifier_kickoff   fichiers plist comparés ; état CHARGÉ non, alors
                           que la ligne s'appelait « LaunchAgents chargés »
        verifier_kickoff   comptage git réussi lu ; ÉCHEC de git rendu comme
                           la même chaîne vide, lue « zéro »
        publish_dashboard  commit refusé et push EXPIRÉ expliqués ; push
                           REJETÉ remontant sans un mot

    « Une règle qu'on se rappelle ne vaut rien face à une règle que l'outil
    applique » — c'est ce que garde_fou.py dit de lui-même depuis le 25/08.
    Le contrôle ajouté ce jour-là applique enfin cette phrase au motif qui a
    produit le plus de défauts de la semaine.

    Il n'en couvre QU'UNE des quatre formes : celle qui se lit dans un arbre
    syntaxique. Les trois autres sont sémantiques, et le dire fait partie du
    contrôle. Ces tests vérifient la forme couverte, dans les deux sens."""

    RACINE = Path(__file__).resolve().parent

    def _lancer_sur(self, contenu):
        """Écrit `contenu` comme un module du dépôt, dans une copie."""
        d = Path(tempfile.mkdtemp(prefix="hindsight-symetrie-"))
        try:
            for nom in ("garde_fou.py", "config.py"):
                shutil.copy(self.RACINE / nom, d / nom)
            (d / "un_module.py").write_text(contenu, encoding="utf-8")
            r = subprocess.run([sys.executable, str(d / "garde_fou.py")],
                               cwd=str(d), capture_output=True, text=True,
                               timeout=120)
            return r.stdout + r.stderr
        finally:
            shutil.rmtree(d, ignore_errors=True)

    ASYMETRIQUE = (
        "import subprocess\n"
        "def publier():\n"
        "    subprocess.run(['git', 'add', '.'], check=True)\n"
        "    try:\n"
        "        subprocess.run(['git', 'push'], check=True)\n"
        "    except subprocess.CalledProcessError:\n"
        "        print('explique')\n"
        "        raise\n")

    def test_une_jumelle_non_protegee_est_signalee(self):
        sortie = self._lancer_sur(self.ASYMETRIQUE)
        self.assertIn("une panne jumelle remonterait sans explication", sortie,
                      "l'asymétrie n'est pas vue :\n%s" % sortie[-700:])
        self.assertIn("publier()", sortie,
                      "la fonction fautive n'est pas nommée :\n%s"
                      % sortie[-700:])

    def test_deux_jumelles_PROTEGEES_ne_declenchent_rien(self):
        """TÉMOIN : un contrôle qui crierait sur tout appel `check=True`
        passerait le test ci-dessus et rendrait le dépôt inutilisable."""
        sortie = self._lancer_sur(
            "import subprocess\n"
            "def publier():\n"
            "    try:\n"
            "        subprocess.run(['git', 'add', '.'], check=True)\n"
            "        subprocess.run(['git', 'push'], check=True)\n"
            "    except subprocess.CalledProcessError:\n"
            "        raise\n")
        self.assertNotIn("une panne jumelle", sortie,
                         "deux appels également protégés sont signalés :\n%s"
                         % sortie[-700:])

    def test_deux_jumelles_NUES_ne_declenchent_rien_non_plus(self):
        """SECOND TÉMOIN, et c'est le sens du contrôle : il cherche une
        ASYMÉTRIE, pas l'absence de handler. Deux appels traités pareil sont
        un choix ; un traité et pas l'autre est un oubli."""
        sortie = self._lancer_sur(
            "import subprocess\n"
            "def publier():\n"
            "    subprocess.run(['git', 'add', '.'], check=True)\n"
            "    subprocess.run(['git', 'push'], check=True)\n")
        self.assertNotIn("une panne jumelle", sortie,
                         "deux appels également nus sont signalés :\n%s"
                         % sortie[-700:])

    def test_un_try_NICHE_dans_une_boucle_n_est_pas_compte_des_deux_cotes(self):
        """LE BUG DE MA PREMIÈRE VERSION, trouvé une heure après l'avoir
        écrite, en prototypant la même idée sur les lectures de fichier :
        certains appels étaient comptés DES DEUX CÔTÉS.

        Elle notait un nœud puis descendait dedans, donc un `try` niché dans
        une boucle était parcouru deux fois — une fois en état « nu » par le
        marquage du parent, une fois en état « protégé » par la descente.
        Sur ce cas construit, elle rendait protégés=[6] et nus=[6, 9] : le
        rapport aurait nommé la ligne 6 comme non protégée alors qu'elle
        l'est.

        Une accusation que le contrôle n'avait pas mesurée — dans le contrôle
        écrit pour trouver exactement ce défaut-là. Aucune occurrence dans le
        dépôt aujourd'hui : le bug était latent, à un refactoring près."""
        import ast, importlib.util
        spec = importlib.util.spec_from_file_location(
            "gf_symetrie", str(self.RACINE / "garde_fou.py"))
        gf = importlib.util.module_from_spec(spec)
        sys.modules["gf_symetrie"] = gf
        try:
            spec.loader.exec_module(gf)
        except SystemExit:
            pass
        source = ("import subprocess\n"
                  "def f(y, a, b):\n"
                  "    for x in y:\n"
                  "        try:\n"
                  "            subprocess.run(a, check=True)\n"
                  "        except Exception:\n"
                  "            pass\n"
                  "    subprocess.run(b, check=True)\n")
        fonction = [n for n in ast.walk(ast.parse(source))
                    if isinstance(n, ast.FunctionDef)][0]
        proteges, nus = gf._appels_verifies(fonction)
        self.assertEqual(sorted(set(proteges) & set(nus)), [],
                         "un même appel est compté protégé ET nu : "
                         "protégés=%s nus=%s" % (proteges, nus))
        self.assertEqual(proteges, [5], "l'appel dans le try est protégé")
        self.assertEqual(nus, [8], "seul l'appel hors du try est nu")

    def test_le_depot_lui_meme_est_symetrique(self):
        """Le contrôle tourne sur le vrai dépôt et doit y être vert : c'est
        ce qui distingue une alerte qu'on peut résoudre d'une alerte qu'on
        apprend à ignorer."""
        r = subprocess.run([sys.executable, str(self.RACINE / "garde_fou.py")],
                           cwd=str(self.RACINE), capture_output=True,
                           text=True, timeout=180)
        self.assertNotIn("une panne jumelle remonterait", r.stdout + r.stderr,
                         "le dépôt porte une asymétrie non résolue")



class TestLaRevendicationDeREFUSEstVerifieeContreLeJOURNAL(unittest.TestCase):
    """« XLK is refused live, every run » apparaît QUATRE FOIS dans le
    README, dont le tableau de tête et le diagramme. C'est la revendication
    la plus visible du dossier — et la plus fragile.

    Mesuré le 29/08 : le désaccord de XLK se joue à **0,024** de Sharpe
    entre deux fenêtres candidates, et il DISPARAÎT si l'on interroge le flux
    IEX au lieu du flux SIP. Quelques séances de données nouvelles peuvent le
    retourner.

    Si cela arrive pendant la semaine jugée, la première ligne que lit un
    juge devient fausse et personne ne le verrait : le tableau de bord
    afficherait simplement un verdict de plus, vert au lieu de rouge.

    État vérifié le 29/08 sur le journal committé : 15 verdicts XLK, 15
    refus, tous par le garde anti-rétrospection, zéro retenu."""

    RACINE = Path(__file__).resolve().parent

    def _lancer(self, lignes_journal, readme=None):
        d = Path(tempfile.mkdtemp(prefix="hindsight-refus-"))
        try:
            for nom in ("garde_fou.py", "config.py"):
                shutil.copy(self.RACINE / nom, d / nom)
            (d / "agent.py").write_text(
                'DEFAULT_UNIVERSE = ["SPY", "XLK"]\n', encoding="utf-8")
            (d / "README.md").write_text(
                readme if readme is not None
                else "# Projet\n\nyes: XLK is refused live, every run, on real bars\n",
                encoding="utf-8")
            with open(d / "decision_log.jsonl", "w", encoding="utf-8") as fh:
                for e in lignes_journal:
                    fh.write(json.dumps(e) + "\n")
            r = subprocess.run([sys.executable, str(d / "garde_fou.py")],
                               cwd=str(d), capture_output=True, text=True,
                               timeout=120)
            return r.stdout + r.stderr
        finally:
            shutil.rmtree(d, ignore_errors=True)

    @staticmethod
    def _passage(tradeable, quand="2026-08-28T19:37:00+00:00"):
        return {"timestamp": quand, "verdicts": [
            {"symbol": "XLK", "tradeable": tradeable, "reason": "peu importe"}]}

    def test_un_seul_verdict_RETENU_fait_tomber_la_phrase(self):
        sortie = self._lancer([self._passage(False), self._passage(True,
                               "2026-09-02T19:37:00+00:00")])
        self.assertIn("n'est plus vrai", sortie,
                      "un XLK retenu ne contredit pas la phrase de tête :\n%s"
                      % sortie[-800:])
        self.assertIn("2026-09-02", sortie,
                      "la date du verdict fautif n'est pas nommée :\n%s"
                      % sortie[-800:])

    def test_tous_refuses_ne_declenche_rien(self):
        """TÉMOIN : un contrôle qui crierait toujours rendrait la phrase
        indéfendable même quand elle est vraie."""
        sortie = self._lancer([self._passage(False), self._passage(False)])
        self.assertNotIn("n'est plus vrai", sortie, sortie[-800:])

    def test_AUCUN_verdict_n_est_pas_une_confirmation(self):
        """SECOND TÉMOIN, et c'est la leçon de la semaine : un journal sans
        aucun verdict pour ce symbole ne CONFIRME pas la phrase — il la rend
        invérifiable, ce qui n'est pas la même chose."""
        sortie = self._lancer([{"timestamp": "2026-08-28T19:37:00+00:00",
                                "verdicts": [{"symbol": "SPY",
                                              "tradeable": True}]}])
        self.assertIn("invérifiable", sortie,
                      "l'absence de preuve passe pour une preuve :\n%s"
                      % sortie[-800:])

    def test_le_TABLEAU_DE_BORD_est_verifie_lui_aussi(self):
        """LE MOTIF DES JUMELLES, dans le contrôle écrit pour d'autres
        jumelles, vingt minutes après.

        La première version ne lisait que `README.md`. Or `docs/index.html`
        porte la MÊME phrase, dans « How to read this page » : « Look for 🛡️
        in the verdicts below — XLK earns it on every run. » C'est la surface
        qu'un juge regarde EN PREMIER, et elle n'était pas couverte."""
        d = Path(tempfile.mkdtemp(prefix="hindsight-refus2-"))
        try:
            for nom in ("garde_fou.py", "config.py"):
                shutil.copy(self.RACINE / nom, d / nom)
            (d / "agent.py").write_text('DEFAULT_UNIVERSE = ["XLK"]\n',
                                        encoding="utf-8")
            # Le README ne dit RIEN : seule la page porte la revendication.
            (d / "README.md").write_text("# Projet\n", encoding="utf-8")
            (d / "docs").mkdir()
            (d / "docs" / "index.html").write_text(
                "<li>it <span>refuses that symbol</span>. Look for the shield "
                "below — XLK earns it on every run.</li>\n", encoding="utf-8")
            with open(d / "decision_log.jsonl", "w", encoding="utf-8") as fh:
                fh.write(json.dumps(self._passage(True)) + "\n")
            r = subprocess.run([sys.executable, str(d / "garde_fou.py")],
                               cwd=str(d), capture_output=True, text=True,
                               timeout=120)
            sortie = r.stdout + r.stderr
            self.assertIn("n'est plus vrai", sortie,
                          "la revendication de la PAGE n'est pas vérifiée :"
                          "\n%s" % sortie[-800:])
            self.assertIn("index.html", sortie,
                          "le fichier fautif n'est pas nommé :\n%s"
                          % sortie[-800:])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_le_separateur_du_kickoff_n_est_PAS_une_revendication(self):
        """TÉMOIN de précision : la page contient aussi « Nothing is hidden —
        every run this project ever logged is still here ». Sans exiger un
        mot de refus ET le symbole dans la même fenêtre, cette phrase-là
        serait prise pour une promesse de refus permanent."""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "gf_revendic", str(self.RACINE / "garde_fou.py"))
        gf = importlib.util.module_from_spec(spec)
        sys.modules["gf_revendic"] = gf
        try:
            spec.loader.exec_module(gf)
        except SystemExit:
            pass
        separateur = ("Nothing is hidden — every run this project ever logged "
                      "is still here, in order.")
        self.assertFalse(gf._revendique_un_refus_permanent(separateur, "XLK"))
        self.assertTrue(gf._revendique_un_refus_permanent(
            "it refuses that symbol — XLK earns it on every run", "XLK"))
        # LA FENÊTRE DE 90 CARACTÈRES EST PORTANTE, et ce cas le prouve :
        # une page RÉELLE contient les deux — une phrase de refus sur XLK
        # quelque part, et bien plus loin le séparateur du kickoff. Sans la
        # borne, le « every run » du séparateur serait rattaché au « refus »
        # d'un autre paragraphe, et le contrôle croirait à une revendication
        # là où il n'y en a pas.
        page = ("XLK was refused here for a reason unrelated to what follows."
                + " filler." * 40
                + " Nothing is hidden — every run this project ever logged is "
                  "still here, in order.")
        self.assertFalse(
            gf._revendique_un_refus_permanent(page, "XLK"),
            "un « every run » éloigné de la phrase de refus est pris pour "
            "une revendication : la borne de 90 caractères ne joue plus")
        # LE MOT DE REFUS EST PORTANT LUI AUSSI. Sans lui, une phrase qui
        # nomme simplement le symbole — « SPY, GLD, XLK and XLV are scored on
        # every run » — deviendrait une promesse de refus permanent, et le
        # contrôle exigerait du journal qu'il ne retienne JAMAIS ce symbole.
        # Trouvé parce que la mutation qui retire cette condition passait
        # tous les autres témoins.
        self.assertFalse(
            gf._revendique_un_refus_permanent(
                "SPY, GLD, XLK and XLV are scored on every run", "XLK"),
            "nommer un symbole près de « every run » suffit à en faire une "
            "revendication de refus")

    def test_sans_revendication_dans_le_README_le_controle_se_tait(self):
        """TROISIÈME TÉMOIN : le contrôle ne connaît pas « XLK » par
        lui-même. Il lit l'univers dans agent.py et la revendication dans le
        README. Sans la phrase, il n'a rien à vérifier."""
        sortie = self._lancer([self._passage(True)],
                              readme="# Projet\n\nRien de particulier.\n")
        self.assertNotIn("n'est plus vrai", sortie, sortie[-800:])



class TestUneANCREMorteEstSignalee(unittest.TestCase):
    """`controle_renvois_resolvent` vérifie que le FICHIER cité existe —
    jamais que l'ANCRE citée mène quelque part.

    L'effet sur un lecteur est le même, et pire : un fichier absent donne une
    404 visible, **une ancre morte ne fait rien**. Le navigateur reste où il
    est, et le lecteur croit avoir mal cliqué.

    Le README en comptait 14 au moment de l'ajout, toutes valides — ce
    contrôle ne corrige donc rien aujourd'hui. Il ferme la moitié qui n'était
    pas vérifiée, comme le contrôle des plists CHARGÉS l'a fait le même jour."""

    RACINE = Path(__file__).resolve().parent

    def _lancer(self, contenu_readme):
        d = Path(tempfile.mkdtemp(prefix="hindsight-ancres-"))
        try:
            for nom in ("garde_fou.py", "config.py"):
                shutil.copy(self.RACINE / nom, d / nom)
            (d / "README.md").write_text(contenu_readme, encoding="utf-8")
            subprocess.run(["git", "init", "-q", "."], cwd=str(d), check=True)
            subprocess.run(["git", "add", "-A"], cwd=str(d), check=True)
            r = subprocess.run([sys.executable, str(d / "garde_fou.py")],
                               cwd=str(d), capture_output=True, text=True,
                               timeout=120)
            return r.stdout + r.stderr
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_une_ancre_qui_ne_mene_nulle_part_est_signalee(self):
        sortie = self._lancer("# Projet\n\nVoir [le détail](#section-absente).\n"
                              "\n## Une autre section\n\nTexte.\n")
        self.assertIn("#section-absente", sortie,
                      "une ancre morte passe inaperçue :\n%s" % sortie[-700:])
        self.assertIn("ne fait RIEN", sortie,
                      "le message n'explique pas pourquoi c'est pire qu'une "
                      "404 :\n%s" % sortie[-700:])

    def test_une_ancre_VALIDE_ne_declenche_rien(self):
        """TÉMOIN : un contrôle qui crierait sur toute ancre rendrait tout
        sommaire impossible."""
        sortie = self._lancer("# Projet\n\nVoir [le détail](#une-autre-section).\n"
                              "\n## Une autre section\n\nTexte.\n")
        self.assertNotIn("ne mene a aucun titre", sortie, sortie[-700:])

    def test_le_balisage_du_titre_est_retire_avant_de_comparer(self):
        """SECOND TÉMOIN, et il a fallu deux essais pour qu'il morde.

        GitHub retire le balisage pour fabriquer l'ancre : « ## Le _mot_
        compte » donne `#le-mot-compte`. Sans ce retrait, le contrôle crierait
        sur une ancre parfaitement valide — le faux positif qui apprend à
        ignorer un garde-fou.

        Ma première version utilisait des accents graves (« Le `code` »). La
        mutation qui supprime le retrait de balisage passait quand même :
        l'expression suivante, qui enlève toute ponctuation, retire déjà les
        accents graves ET les astérisques. Le SEUL caractère de balisage
        qu'elle laisse est le tiret bas, parce qu'il fait partie de `\\w`.
        C'est donc lui, et lui seul, que ce témoin doit exercer."""
        sortie = self._lancer("# Projet\n\nVoir [ici](#le-mot-compte).\n"
                              "\n## Le _mot_ compte\n\nTexte.\n")
        self.assertNotIn("ne mene a aucun titre", sortie, sortie[-700:])

    def test_les_ancres_du_README_reel_resolvent_toutes(self):
        """Le contrôle tourne sur le vrai dépôt et doit y être vert : c'est
        ce qui distingue une alerte résoluble d'une alerte qu'on apprend à
        ignorer."""
        r = subprocess.run([sys.executable, str(self.RACINE / "garde_fou.py")],
                           cwd=str(self.RACINE), capture_output=True,
                           text=True, timeout=180)
        self.assertNotIn("ne mene a aucun titre", r.stdout + r.stderr,
                         "le dépôt porte une ancre morte")



class TestUnHorodatageNaifEstSignaleParLeGardeFou(unittest.TestCase):
    """`datetime.fromisoformat("2026-08-28T14:00:00")` ne lève RIEN : elle
    rend un datetime naïf. La panne arrive une ligne plus loin, à la
    comparaison. Le `try` autour de l'analyse est visé une ligne trop tôt.

    Cinquième occurrence en une session du motif « une règle appliquée ici
    mais pas à son jumeau », et la seconde qui se lise dans un arbre
    syntaxique. Condition posée avant de l'ajouter, et vérifiée : rejouée sur
    l'arbre d'avant les corrections du 29/08, la règle crie sur les trois
    sites fautifs et sur eux seuls ; rejouée sur l'arbre corrigé, elle se tait
    entièrement."""

    RACINE = Path(__file__).resolve().parent
    MOTIF = "sans garantir son fuseau"
    MOTIF_NOW = "lit le fuseau SUR la valeur analysee"

    def _lancer(self, corps_python):
        d = Path(tempfile.mkdtemp(prefix="hindsight-fuseau-"))
        try:
            for nom in ("garde_fou.py", "config.py"):
                shutil.copy(self.RACINE / nom, d / nom)
            (d / "sujet.py").write_text(
                "from datetime import datetime, timezone\n\n" + corps_python,
                encoding="utf-8")
            subprocess.run(["git", "init", "-q", "."], cwd=str(d), check=True)
            subprocess.run(["git", "add", "-A"], cwd=str(d), check=True)
            r = subprocess.run([sys.executable, str(d / "garde_fou.py")],
                               cwd=str(d), capture_output=True, text=True,
                               timeout=180)
            return r.stdout + r.stderr
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_une_analyse_sans_parade_est_signalee(self):
        sortie = self._lancer(
            "def age(brut, debut):\n"
            "    t = datetime.fromisoformat(brut)\n"
            "    return t >= debut\n")
        self.assertIn(self.MOTIF, sortie, sortie[-900:])
        self.assertIn("age()", sortie, sortie[-900:])

    def test_normaliser_par_replace_suffit(self):
        """TÉMOIN 1a : la parade d'`agent.py` et de `bilan_semaine.py`.

        SÉPARÉ de 1b après mesure : mon témoin d'origine employait les DEUX
        reconnaisseurs à la fois (`t.tzinfo is None` ET `replace(tzinfo=)`).
        Supprimer l'un des deux dans le contrôle ne faisait donc échouer
        aucun test — l'autre couvrait. Deux mutations survivaient sur un
        témoin qui avait l'air de les couvrir."""
        sortie = self._lancer(
            "def age(brut, debut):\n"
            "    t = datetime.fromisoformat(brut).replace(tzinfo=timezone.utc)\n"
            "    return t >= debut\n")
        self.assertNotIn(self.MOTIF, sortie, sortie[-900:])

    def test_tester_tzinfo_is_None_suffit(self):
        """TÉMOIN 1b : l'autre moitié, seule."""
        sortie = self._lancer(
            "def age(brut, debut):\n"
            "    t = datetime.fromisoformat(brut)\n"
            "    if t.tzinfo is None:\n"
            "        return None\n"
            "    return t >= debut\n")
        self.assertNotIn(self.MOTIF, sortie, sortie[-900:])

    def test_rattraper_le_TypeError_suffit(self):
        """TÉMOIN 2 sur 4 : la parade de `monitor_exits.py`, qui traite la
        comparaison impossible comme « dû », pas comme « silencieux »."""
        sortie = self._lancer(
            "def age(brut, debut):\n"
            "    t = datetime.fromisoformat(brut)\n"
            "    try:\n"
            "        return t >= debut\n"
            "    except TypeError:\n"
            "        return True\n")
        self.assertNotIn(self.MOTIF, sortie, sortie[-900:])

    def test_analyser_une_CONSTANTE_en_majuscules_suffit(self):
        """TÉMOIN 3 sur 4 : la parade du garde-fou lui-même — `KICKOFF_UTC`
        est un littéral qui porte son fuseau et ne peut pas dériver."""
        sortie = self._lancer(
            'KICKOFF = "2026-08-28T15:00:00+00:00"\n\n'
            "def age(debut):\n"
            "    return datetime.fromisoformat(KICKOFF) >= debut\n")
        self.assertNotIn(self.MOTIF, sortie, sortie[-900:])

    def test_now_sur_le_fuseau_analyse_est_signale_MALGRE_l_apparence(self):
        """TÉMOIN 4, et c'est celui qui justifie tout le contrôle.

        `datetime.now(valeur.tzinfo)` RESSEMBLE à une parade : elle ne lève
        jamais de TypeError. Elle n'évite pas le problème, elle le rend
        silencieux — et du côté qui AUTORISE. Mesuré le 29/08 sur la porte de
        fraîcheur : une barre vieille de 5 j 3 h, limite à 5 jours, REFUSÉE à
        Paris et à UTC, ACCEPTÉE à Los Angeles et à Honolulu."""
        sortie = self._lancer(
            "def age(brut):\n"
            "    t = datetime.fromisoformat(brut)\n"
            "    return (datetime.now(t.tzinfo) - t).days\n")
        self.assertIn(self.MOTIF_NOW, sortie, sortie[-900:])

    def test_une_docstring_qui_CITE_la_parade_ne_vaut_pas_parade(self):
        """SECOND TÉMOIN sur la lecture : la première version de ce contrôle
        cherchait des sous-chaînes et exemptait `_horodatage_utc`
        d'`alpaca_cli.py` — parce que sa docstring CITE le défaut qu'elle
        corrige. Le contrôle lit l'arbre, pas le texte."""
        sortie = self._lancer(
            "def age(brut, debut):\n"
            '    """On pourrait ecrire t.replace(tzinfo=timezone.utc) ici,\n'
            '    ou attraper TypeError. On ne le fait pas."""\n'
            "    t = datetime.fromisoformat(brut)\n"
            "    return t >= debut\n")
        self.assertIn(self.MOTIF, sortie, sortie[-900:])

    def test_le_depot_reel_est_vert_sur_ce_controle(self):
        """Une alerte qu'on ne peut pas résoudre apprend à ignorer les
        alertes. Celle-ci doit être verte sur le dépôt aujourd'hui."""
        r = subprocess.run([sys.executable, str(self.RACINE / "garde_fou.py")],
                           cwd=str(self.RACINE), capture_output=True,
                           text=True, timeout=240)
        sortie = r.stdout + r.stderr
        self.assertNotIn(self.MOTIF, sortie, sortie[-900:])
        self.assertNotIn(self.MOTIF_NOW, sortie, sortie[-900:])



class TestLeMoteurDeRenduDuDeckDitCeQuIlNeSaitPasFaire(unittest.TestCase):
    """`submission/rendre_le_deck.py` existe parce que cette machine n'a aucun
    moteur de rendu — ni LibreOffice, ni pdftoppm, ni markitdown — et que la
    mise en page du deck était donc la seule chose du dossier que personne ne
    pouvait vérifier.

    Les deux tests ci-dessous gardent les DEUX défauts que ce script a eus
    dans sa propre première version, tous deux du genre que ce dépôt traque."""

    RACINE = Path(__file__).resolve().parent
    SCRIPT = RACINE / "submission" / "rendre_le_deck.py"

    def _lancer(self):
        d = Path(tempfile.mkdtemp(prefix="hindsight-rendu-"))
        try:
            r = subprocess.run(
                [sys.executable, str(self.SCRIPT),
                 "--sortie", str(d / "apercu.html")],
                cwd=str(self.RACINE), capture_output=True, text=True,
                timeout=180)
            return r.returncode, r.stdout + r.stderr
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_le_graphique_NON_RENDU_est_annonce(self):
        """Le rapport « ce qui n'a pas été rendu fidèlement » annonçait ZÉRO
        problème alors que le graphique de la slide 8 n'était pas rendu :
        `_geometrie` ne lisait que `a:xfrm`, or un `p:graphicFrame` porte la
        sienne sous `p:xfrm`. Elle rendait None, l'appelant faisait
        `continue`, et le seul élément que ce script ne sait pas rendre était
        aussi le seul qu'il oubliait de signaler.

        C'est exactement le motif de ce dépôt : un événement réel qui perd sa
        trace dans la comptabilité censée le suivre."""
        d = Path(tempfile.mkdtemp(prefix="hindsight-rendu3-"))
        try:
            cible = d / "apercu.html"
            r = subprocess.run([sys.executable, str(self.SCRIPT),
                                "--sortie", str(cible)], cwd=str(self.RACINE),
                               capture_output=True, text=True, timeout=180)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie[-600:])
            self.assertIn("graphique OOXML", sortie,
                          "le script ne dit plus qu'il ne rend pas le "
                          "graphique :\n%s" % sortie[-800:])
            # ET il faut que sa PLACE soit visible sur le rendu, sinon le
            # lecteur regarde une slide 8 amputee sans le voir. C'est cette
            # moitie-la qui exige de lire `p:xfrm` : le message, lui, part
            # desormais sans condition.
            page = cible.read_text(encoding="utf-8")
            self.assertIn("GRAPHIQUE NON RENDU", page,
                          "le message annonce le graphique mais rien ne "
                          "marque sa place sur le rendu")
            self.assertNotIn("n'a meme pas de geometrie lisible", sortie,
                             "la geometrie du graphique n'est plus lue")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_une_boite_plus_etroite_que_ses_marges_n_est_pas_un_debordement(self):
        """Les quatre flèches décoratives de la slide 4 vivent dans des boîtes
        de 10 pt de large alors que les marges internes par défaut d'OOXML en
        font 14,4. La largeur disponible est donc NÉGATIVE et le texte déborde
        par construction.

        Ma première version les comptait comme « 22 pt trop large » — quatre
        fausses alertes sur dix. Une mesure impossible n'est pas une mesure
        ratée : elle se dit, elle ne se convertit pas en verdict. Un outil qui
        crie sur ce qu'il n'a pas su mesurer apprend à être ignoré."""
        _code, sortie = self._lancer()
        self.assertIn("non mesure", sortie, sortie[-800:])
        bloc = sortie.split("non mesure")[0]
        self.assertNotIn("forme 8 ", bloc,
                         "une flèche décorative est comptée comme un "
                         "débordement :\n%s" % bloc[-800:])

    def test_une_collision_deja_presente_n_est_pas_imputee_au_debordement(self):
        """Ma première version annonçait « le débord recouvre la forme 1 » sur
        la slide 4. Vérifié à la main : les deux boîtes se chevauchent DÉJÀ
        (43–77 contre 72–158) sans qu'aucun texte ne déborde. Elle nommait les
        bonnes formes pour la mauvaise raison.

        « Ce débordement casse quelque chose » est exactement le genre
        d'affirmation qu'un lecteur croit sur parole : elle doit donc être
        causale, pas coïncidente."""
        _code, sortie = self._lancer()
        for ligne in sortie.splitlines():
            if "RECOUVRE" in ligne:
                self.fail("une collision est imputée au débordement alors "
                          "qu'aucune ne l'est aujourd'hui : %s" % ligne.strip())

    def test_l_exactitude_est_annoncee_PAR_ZONE_et_pas_globalement(self):
        """Carlito et Caladea sont les clones libres métriquement compatibles
        de Calibri et Cambria. Carlito déclare upem=2048, asc=1950,
        desc=-550 — les valeurs exactes de Calibri, et le script le VÉRIFIE
        au lieu de le croire.

        Ma première version gardait un seul drapeau « exactes » pour tout le
        deck. Une seule famille sans référence locale (Cambria, 35 emplois)
        faisait annoncer « mesure approchée » sur les 128 zones en Calibri,
        qui sont mesurées exactement. Un fait par élément, résumé en un
        drapeau unique, redevient faux pour presque tous — c'est le motif que
        ce dépôt attrape le plus souvent."""
        _code, sortie = self._lancer()
        self.assertIn("VERIFIE", sortie,
                      "la compatibilité métrique n'est plus vérifiée :\n%s"
                      % sortie[-900:])
        self.assertIn("mesure exacte", sortie,
                      "aucune zone n'est annoncée comme mesurée exactement, "
                      "alors que Calibri est vérifiée :\n%s" % sortie[-900:])
        self.assertIn("PAR ZONE", sortie,
                      "le seuil ne se dit plus par zone")

    def test_le_rendu_produit_bien_les_onze_diapos(self):
        """TÉMOIN : un script qui n'écrirait rien passerait les deux tests
        précédents."""
        d = Path(tempfile.mkdtemp(prefix="hindsight-rendu2-"))
        try:
            cible = d / "apercu.html"
            subprocess.run([sys.executable, str(self.SCRIPT),
                            "--sortie", str(cible)], cwd=str(self.RACINE),
                           capture_output=True, text=True, timeout=180)
            page = cible.read_text(encoding="utf-8")
            self.assertEqual(page.count('class="slide"'), 11, "11 diapos "
                             "attendues, %d rendues" % page.count('class="slide"'))
            self.assertIn("WHERE THIS SITS IN THE FIELD", page)
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
