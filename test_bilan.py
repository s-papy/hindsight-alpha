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
            self.assertIn("aucun verdict dans la fenetre", sortie,
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
            self.assertIn("garde anti-retrospection", sortie)
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
            self.assertIn("MANQUANT", sortie,
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
            self.assertIn("INCONNUE", sortie)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
