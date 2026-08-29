#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha
#
# Sous licence MIT, redistribuer ce fichier -- entier ou par morceaux --
# OBLIGE a conserver cet avis. C'est la seule contrainte de la licence, et
# c'est la raison d'etre de ces trois lignes : un fichier copie-colle
# emporte desormais sa provenance avec lui.
"""Tests de `bilan_semaine.py` — le compte rendu de la semaine live.

Ce qui se joue ici n'est pas la mise en forme : c'est que le bilan ne
puisse pas ETRE FLATTE. Trois proprietes, et la premiere porte tout le
reste :

  . la FENETRE est respectee. Les essais d'avant le kickoff ne doivent
    jamais entrer dans le decompte : ce sont eux qui ont servi a mettre au
    point la strategie, les compter transformerait un resultat hors
    echantillon en auto-evaluation ;
  . un passage MANQUANT est signale. Un agent qui n'a pas tourne n'a rien
    prouve, et un bilan qui n'en dit rien laisse croire au contraire ;
  . une fenetre ILLISIBLE fait ARRETER le script. « Je ne sais pas quelles
    entrees comptent » ne doit jamais devenir « je les compte toutes ».
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent


class BaseBilan(unittest.TestCase):
    KICKOFF = "2026-08-28T15:00:00+00:00"

    def _dossier(self, entrees, kickoff=KICKOFF, etat=None):
        d = Path(tempfile.mkdtemp(prefix="hindsight-bilan-"))
        for nom in ("bilan_semaine.py",):
            (d / nom).write_bytes((RACINE / nom).read_bytes())
        with open(d / "decision_log.jsonl", "w", encoding="utf-8") as fh:
            for e in entrees:
                fh.write(json.dumps(e) + "\n")
        if kickoff is not None:
            (d / "kickoff_freeze.json").write_text(
                json.dumps({"kickoff": kickoff, "valeurs": {}}), encoding="utf-8")
        (d / "state.json").write_text(
            json.dumps(etat or {"starting_equity": 100000.0}), encoding="utf-8")
        return d

    def _lancer(self, d):
        r = subprocess.run([sys.executable, str(d / "bilan_semaine.py")],
                           cwd=str(d), capture_output=True, text=True, timeout=120)
        return r.returncode, r.stdout + r.stderr

    def _passage(self, quand, symbole="XLK", tradeable=False,
                 motif="hindsight_guard: windows disagree"):
        return {"run_type": "agent", "timestamp": quand,
                "outcome": "no_trade",
                "verdicts": [{"symbol": symbole, "tradeable": tradeable,
                              "reason": motif}]}


class TestLaFenetreEstRespectee(BaseBilan):

    def test_un_passage_AVANT_le_kickoff_n_est_pas_compte(self):
        """LE test qui porte tout le reste.

        Les 21 passages d'avant le 28/08 ont servi a mettre au point la
        strategie. Les compter dans le bilan transformerait le seul
        resultat hors echantillon du dossier en auto-evaluation."""
        d = self._dossier([self._passage("2026-08-27T19:37:00+00:00")])
        try:
            code, sortie = self._lancer(d)
            self.assertEqual(code, 0)
            self.assertIn("no verdict inside the window", sortie,
                          "un passage anterieur au kickoff entre dans le "
                          "decompte :\n%s" % sortie)
        finally:
            __import__("shutil").rmtree(d, ignore_errors=True)

    def test_un_passage_DANS_la_fenetre_est_compte(self):
        """TEMOIN. Sans lui, un script qui ne compterait RIEN passerait le
        test ci-dessus — et le bilan serait vide toute la semaine."""
        d = self._dossier([self._passage("2026-08-28T19:37:00+00:00")])
        try:
            code, sortie = self._lancer(d)
            self.assertEqual(code, 0)
            self.assertIn("hindsight guard", sortie)
            self.assertIn("XLK", sortie)
        finally:
            __import__("shutil").rmtree(d, ignore_errors=True)


class TestUnPassageManquantEstDIT(BaseBilan):

    def test_zero_passage_dans_une_fenetre_ouverte_est_signale(self):
        """Un agent qui n'a pas tourne n'a rien prouve. Le bilan doit le
        dire, sinon une liste de refus vide se lit comme « rien a
        signaler »."""
        hier = (datetime.now(timezone.utc) - timedelta(days=2))
        d = self._dossier([], kickoff=hier.isoformat())
        try:
            code, sortie = self._lancer(d)
            self.assertIn("MISSING", sortie,
                          "aucun passage n'a eu lieu et le bilan n'en dit "
                          "rien :\n%s" % sortie)
        finally:
            __import__("shutil").rmtree(d, ignore_errors=True)


class TestUneFenetreILLISIBLE_ARRETE_le_bilan(BaseBilan):

    def test_sans_kickoff_le_script_refuse_de_conclure(self):
        """« Je ne sais pas quelles entrees comptent » ne doit jamais
        devenir « je les compte toutes ». Compter tout le journal
        melangerait les essais d'avant le kickoff au resultat hors
        echantillon — precisement ce que ce depot existe pour empecher."""
        d = self._dossier([self._passage("2026-08-28T19:37:00+00:00")],
                          kickoff=None)
        try:
            code, sortie = self._lancer(d)
            self.assertNotEqual(code, 0,
                                "le bilan conclut sans savoir quelle fenetre "
                                "compter :\n%s" % sortie)
            self.assertIn("WINDOW UNKNOWN", sortie)
            # UN REFUS N'EST PAS UN PLANTAGE. Ajoute apres mutation : une
            # version qui supprimait le refus deliberait tombait quand meme
            # en TypeError deux lignes plus bas, donc `code != 0` restait
            # vrai et ce test passait POUR UNE MAUVAISE RAISON. C'est la
            # distinction que tout ce depot tient : « je refuse » et « je me
            # suis casse » ne se disent pas pareil.
            self.assertNotIn("Traceback", sortie,
                             "le bilan PLANTE au lieu de refuser proprement :"
                             "\n%s" % sortie[-800:])
        finally:
            __import__("shutil").rmtree(d, ignore_errors=True)



class TestLeRapportEstLISIBLE(BaseBilan):
    """LIVE_WEEK.md est en anglais et envoie le lecteur ici : « Where the
    numbers come from : python3 bilan_semaine.py ». Le rapport sortait en
    francais. C'est le livrable du 04/09, celui qu'un juge d'un hackathon
    international lit apres avoir suivi l'instruction."""

    def test_le_rapport_sort_en_anglais(self):
        d = self._dossier([self._passage("2026-08-28T19:37:00+00:00")])
        try:
            code, sortie = self._lancer(d)
            self.assertEqual(code, 0)
            self.assertIn("LIVE WEEK REPORT", sortie, sortie)
            # LES TITRES SONT VERIFIES AVEC LEUR NUMERO, pas seulement dans
            # l'ordre ou ils sortent. Ma premiere version ne comparait que les
            # positions dans le texte : renumeroter « 0. P&L » et « 9. THE
            # REFUSAL MECHANISM » la laissait VERTE, alors qu'un juge lit les
            # numeros et y verrait l'inverse exact de l'engagement pris.
            titres = ("1. THE REFUSAL MECHANISM", "2. EXECUTION REGULARITY",
                      "3. ENTRIES", "4. P&L")
            for attendu in titres:
                self.assertIn(attendu, sortie,
                              "titre manquant ou renumerote : %r\n%s"
                              % (attendu, sortie))
            positions = [sortie.index(t) for t in titres]
            self.assertEqual(positions, sorted(positions),
                             "l'ordre annonce dans LIVE_WEEK.md n'est plus "
                             "celui du rapport :\n%s" % sortie)
        finally:
            __import__("shutil").rmtree(d, ignore_errors=True)

    def test_les_lignes_illisibles_sont_comptees_MEME_A_ZERO(self):
        """LIVE_WEEK.md promet publiquement : « Unreadable log lines are
        skipped AND COUNTED IN THE OUTPUT ». Le compte ne s'imprimait que
        s'il y en avait -- la phrase n'etait donc vraie que dans ce cas, et
        un lecteur ne pouvait pas distinguer « aucune » de « pas verifie »."""
        d = self._dossier([self._passage("2026-08-28T19:37:00+00:00")])
        try:
            code, sortie = self._lancer(d)
            self.assertIn("unreadable log lines skipped: 0", sortie,
                          "a zero, le rapport ne dit plus rien des lignes "
                          "illisibles :\n%s" % sortie)
        finally:
            __import__("shutil").rmtree(d, ignore_errors=True)

    def test_une_ligne_illisible_est_comptee_et_le_rapport_continue(self):
        """TEMOIN : imprimer « 0 » en dur passerait le test ci-dessus."""
        d = self._dossier([self._passage("2026-08-28T19:37:00+00:00")])
        try:
            journal = d / "decision_log.jsonl"
            journal.write_text(journal.read_text(encoding="utf-8")
                               + "{ceci n'est pas du json\n", encoding="utf-8")
            code, sortie = self._lancer(d)
            self.assertEqual(code, 0)
            self.assertIn("unreadable log lines skipped: 1", sortie, sortie)
            self.assertIn("XLK", sortie,
                          "une ligne illisible a emporte le reste du rapport")
        finally:
            __import__("shutil").rmtree(d, ignore_errors=True)

    def test_l_aide_est_lisible_et_en_anglais(self):
        """`description=__doc__` deversait la docstring francaise dans --help,
        reflowee par argparse : la liste numerotee de l'ordre -- qui est tout
        l'engagement de LIVE_WEEK.md -- sortait en un pave illisible."""
        d = self._dossier([self._passage("2026-08-28T19:37:00+00:00")])
        try:
            r = subprocess.run([sys.executable, str(d / "bilan_semaine.py"),
                                "--help"], cwd=str(d), capture_output=True,
                               text=True, timeout=60)
            sortie = r.stdout + r.stderr
            self.assertEqual(r.returncode, 0, sortie)
            self.assertIn("1. the refusal mechanism", sortie, sortie)
            self.assertIn("4. P&L", sortie, sortie)
            self.assertIn("LIVE_WEEK.md", sortie,
                          "l'aide ne renvoie plus a l'engagement qu'elle "
                          "resume :\n%s" % sortie)
            # TEMOIN inclus : la docstring francaise ne doit plus s'y
            # deverser. « POURQUOI CE FICHIER EXISTE » en est le titre.
            self.assertNotIn("POURQUOI CE FICHIER EXISTE", sortie,
                             "la docstring interne repart dans --help :\n%s"
                             % sortie)
        finally:
            __import__("shutil").rmtree(d, ignore_errors=True)

    def test_un_pourcentage_nomme_sa_base(self):
        """Le denominateur est le TOTAL des verdicts, retenus compris. Sous
        un titre « refused », les pourcentages ne font donc pas 100 % : un
        lecteur qui les somme trouve 75 % et cherche l'erreur. Un
        pourcentage sans sa base est une invitation a se tromper."""
        d = self._dossier([self._passage("2026-08-28T19:37:00+00:00")])
        try:
            code, sortie = self._lancer(d)
            self.assertIn("of all verdicts", sortie,
                          "les pourcentages ne disent plus sur quoi ils "
                          "portent :\n%s" % sortie)
        finally:
            __import__("shutil").rmtree(d, ignore_errors=True)



class TestUnJournalILLISIBLENAccusePersonne(BaseBilan):
    """REPRODUIT le 29/08/2026, avec decision_log.jsonl simplement ABSENT :

        unreadable log lines skipped: -1

        2. EXECUTION REGULARITY
           0 actual run(s) for 1 expected
           🔴 1 run(s) MISSING — an agent that did not run proved nothing

    ...et un code de sortie 0. Une ACCUSATION contre l'agent, produite par
    l'incapacite a lire un fichier. Le -1 etait un sentinelle interne parti
    tel quel dans le rapport public.

    Et dans le MEME rapport, quatre lignes plus haut, la section 1 disait
    correctement « ⬜ no verdict — UNKNOWN, not zero ». La meme absence, lue
    de deux facons opposees.

    Le fichier de gel, l'autre entree de ce script, avait DEJA le bon
    traitement : illisible, on s'arrete. La regle etait ecrite pour un
    jumeau et pas pour l'autre."""

    def test_un_journal_absent_arrete_le_bilan(self):
        d = self._dossier([self._passage("2026-08-28T19:37:00+00:00")])
        try:
            (d / "decision_log.jsonl").unlink()
            code, sortie = self._lancer(d)
            self.assertEqual(code, 2,
                             "un bilan sans donnees sort en 0 :\n%s" % sortie)
            self.assertIn("LOG UNREADABLE", sortie, sortie)
            # ASSERTIONS RESSERREES : ma premiere version cherchait
            # « MISSING » n'importe ou et le trouvait dans le message
            # d'arret lui-meme, qui explique justement ce qu'il evite. On
            # vise la LIGNE d'accusation, pas le mot.
            self.assertNotIn("run(s) MISSING", sortie,
                             "l'agent est accuse d'avoir manque des passages "
                             "alors que le journal n'a pas pu etre lu :\n%s"
                             % sortie)
            self.assertNotIn("EXECUTION REGULARITY", sortie,
                             "la section qui accuse est quand meme rendue :"
                             "\n%s" % sortie)
            self.assertNotIn("skipped: -1", sortie,
                             "la sentinelle interne part dans le rapport "
                             "public :\n%s" % sortie)
        finally:
            __import__("shutil").rmtree(d, ignore_errors=True)

    def test_un_journal_VIDE_reste_une_mesure(self):
        """TEMOIN, et c'est la distinction entiere : un fichier qui EXISTE et
        ne contient rien a bien ete lu. « 0 passage » est alors une mesure,
        et l'agent doit etre signale comme manquant -- s'arreter la serait
        aussi faux que d'accuser tout a l'heure."""
        d = self._dossier([])
        try:
            code, sortie = self._lancer(d)
            self.assertEqual(code, 0, sortie)
            self.assertIn("MISSING", sortie,
                          "un journal vide ne signale plus les passages "
                          "manquants :\n%s" % sortie)
            self.assertIn("unreadable log lines skipped: 0", sortie, sortie)
        finally:
            __import__("shutil").rmtree(d, ignore_errors=True)



class TestLeMessageNeNommePasUneCauseNonMESUREE(BaseBilan):
    """La section P&L avait UN seul texte pour toutes les facons de ne pas
    connaitre l'equite de depart : « starting equity UNKNOWN (state.json
    unreadable) ».

    Mesure le 29/08/2026, trois situations differentes, message identique :

        state.json LISIBLE sans le champ  -> « unreadable »  (faux)
        starting_equity = 0.0             -> « unreadable »  (doublement
                                             faux : lisible, present, et
                                             une valeur)
        fichier vraiment absent           -> « unreadable »  (enfin vrai)

    Et 0.0 est precisement la ligne de base corrompue que
    `risk_gates._record_starting_equity` a appris a REFUSER le 28/08 -- le
    verrou de perte hebdomadaire se calcule dessus. Si elle arrivait quand
    meme ici, le rapport accusait le fichier au lieu de montrer la valeur."""

    def _pnl(self, etat):
        d = self._dossier([self._passage("2026-08-28T19:37:00+00:00")],
                          etat=etat)
        try:
            if etat is False:                       # cas « fichier absent »
                (d / "state.json").unlink()
            code, sortie = self._lancer(d)
            self.assertEqual(code, 0, sortie)
            return next(l.strip() for l in sortie.splitlines()
                        if "starting equity" in l)
        finally:
            __import__("shutil").rmtree(d, ignore_errors=True)

    def test_un_fichier_lisible_sans_le_champ_ne_dit_pas_illisible(self):
        ligne = self._pnl({"consecutive_losses": 0})
        self.assertIn("carries no starting_equity", ligne, ligne)
        self.assertNotIn("could not be opened", ligne,
                         "le rapport accuse le fichier d'etre illisible "
                         "alors qu'il vient de le lire : %s" % ligne)

    def test_une_equite_de_depart_a_zero_est_MONTREE_pas_qualifiee_d_inconnue(self):
        """C'est la valeur que risk_gates refuse d'enregistrer depuis le
        28/08, parce qu'elle desactive le verrou de perte hebdomadaire :
        une base a 0 rend tout drawdown nul. La montrer est le seul moyen de
        la faire corriger."""
        ligne = self._pnl({"starting_equity": 0.0})
        self.assertIn("0.0", ligne, ligne)
        self.assertIn("risk_gates refuses", ligne, ligne)
        self.assertNotIn("could not be opened", ligne, ligne)

    def test_une_valeur_non_numerique_est_nommee_telle_quelle(self):
        ligne = self._pnl({"starting_equity": "cent mille"})
        self.assertIn("not a number", ligne, ligne)
        self.assertIn("cent mille", ligne,
                      "la valeur fautive n'est pas montree : %s" % ligne)

    def test_un_fichier_vraiment_absent_le_dit(self):
        """TEMOIN : a force de distinguer, il ne faut pas perdre le seul cas
        ou « je n'ai pas pu ouvrir » etait vrai."""
        ligne = self._pnl(False)
        self.assertIn("could not be opened", ligne, ligne)
        self.assertIn("FileNotFoundError", ligne, ligne)

    def test_une_equite_valide_reste_affichee(self):
        """SECOND TEMOIN : a force de refuser, ne plus rien afficher
        passerait tous les tests ci-dessus."""
        ligne = self._pnl({"starting_equity": 100000.0})
        self.assertIn("100000.00", ligne, ligne)
        self.assertNotIn("UNKNOWN", ligne, ligne)


if __name__ == "__main__":
    unittest.main(verbosity=2)
