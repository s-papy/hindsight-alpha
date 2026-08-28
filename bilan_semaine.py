#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha
#
# Sous licence MIT, redistribuer ce fichier -- entier ou par morceaux --
# OBLIGE a conserver cet avis.
"""Le bilan de la semaine live, CALCULE et non redige.

POURQUOI CE FICHIER EXISTE, ET POURQUOI MAINTENANT
===================================================
Ecrit le 28/08/2026 au soir, apres le PREMIER passage de l'agent et avant
d'en connaitre le resultat. C'est deliberé.

Ce depot entier repose sur une idee : un parametre choisi apres avoir vu
les donnees ne prouve rien. `hindsight_guard.check_selection_leakage`
applique cette idee au choix de la fenetre de volatilite. Ce script
l'applique au COMPTE RENDU : la liste des chiffres rapportes est figee
AVANT que la semaine ait produit son resultat.

Sans lui, le 04/09, la tentation serait de choisir quoi montrer une fois
les chiffres connus -- de mettre en avant la metrique qui flatte. Ce n'est
pas une accusation, c'est le comportement par defaut de quiconque redige
un bilan. La seule protection est de s'engager avant.

CE QUI EST RAPPORTE, ET DANS CET ORDRE
=======================================
1. Le mecanisme de refus       -- combien de fois le garde anti-retrospection
                                  a refuse un symbole, et lequel. C'est le
                                  RESULTAT que le README annonce comme
                                  « celui qui merite d'etre juge ».
2. La regularite d'execution   -- passages attendus contre passages reels.
                                  Un agent qui n'a pas tourne n'a rien prouve.
3. Les entrees                 -- ordres soumis, refus des gardes de risque.
4. Le P&L                      -- EN DERNIER, et assume comme tel. Sur cinq
                                  seances et une poignee de trades, il ne
                                  distingue pas une strategie d'un tirage.

Cet ordre est fige ici. Il ne sera pas reordonne le 04/09 selon ce qui
flatte le plus.

CE QUE CE SCRIPT NE PEUT PAS FAIRE
===================================
Il ne juge pas si la strategie est bonne. Il compte ce qui s'est passe.
Un mecanisme de refus qui fonctionne parfaitement sur une strategie sans
edge reste un mecanisme de refus qui fonctionne : c'est exactement ce que
ce depot pretend demontrer, et rien de plus.

    python3 bilan_semaine.py            # depuis le journal seul
    python3 bilan_semaine.py --reseau   # + l'equite reelle chez Alpaca

Ne modifie RIEN. Il lit, il compte, il dit.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

RACINE = os.path.dirname(os.path.abspath(__file__))
JOURNAL = os.path.join(RACINE, "decision_log.jsonl")
ETAT = os.path.join(RACINE, "state.json")
GEL = os.path.join(RACINE, "kickoff_freeze.json")

# L'agent est planifie a 19:37 UTC, du lundi au vendredi.
HEURE_AGENT = (19, 37)


def _lire_journal() -> list:
    """Une ligne illisible est SAUTEE, pas fatale -- meme choix que partout
    ailleurs dans ce depot. Mais on COMPTE les sautees et on le dit : un
    bilan qui ignore silencieusement une partie de ses donnees n'est pas un
    bilan."""
    entrees, illisibles = [], 0
    try:
        with open(JOURNAL, encoding="utf-8") as fh:
            for ligne in fh:
                if not ligne.strip():
                    continue
                try:
                    entrees.append(json.loads(ligne))
                except json.JSONDecodeError:
                    illisibles += 1
    except OSError:
        return [], -1
    return entrees, illisibles


def _fenetre() -> "tuple[datetime, datetime] | None":
    """La semaine live : du kickoff a la date limite. Lue dans le fichier de
    gel, pas ecrite ici -- une date en dur serait une seconde source de
    verite, et elles finissent toujours par diverger."""
    try:
        with open(GEL, encoding="utf-8") as fh:
            kickoff = json.load(fh).get("kickoff")
        debut = datetime.fromisoformat(str(kickoff).replace("Z", "+00:00"))
    except (OSError, ValueError, AttributeError, json.JSONDecodeError):
        return None
    return debut, debut + timedelta(days=7)


def _passages_attendus(debut: datetime, fin: datetime) -> int:
    """Combien de fois l'agent AURAIT du tourner d'ici a maintenant."""
    borne = min(fin, datetime.now(timezone.utc))
    n, jour = 0, debut
    while jour <= borne and n < 40:
        prevu = jour.replace(hour=HEURE_AGENT[0], minute=HEURE_AGENT[1],
                             second=0, microsecond=0)
        if debut <= prevu <= borne and prevu.weekday() < 5:
            n += 1
        jour += timedelta(days=1)
    return n


def _categorie(motif: str) -> str:
    if re.search(r"hindsight[_ ]guard", motif, re.I):
        return "garde anti-retrospection"
    if re.search(r"volatility not cheap|regime", motif, re.I):
        return "regime de volatilite"
    return "autre"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reseau", action="store_true",
                   help="interroge Alpaca pour l'equite reelle")
    args = p.parse_args()

    entrees, illisibles = _lire_journal()
    fenetre = _fenetre()

    print()
    print("=" * 74)
    print("BILAN DE LA SEMAINE LIVE — %s" % datetime.now().strftime("%d/%m/%Y %H:%M"))
    print("=" * 74)

    if fenetre is None:
        print("  🔴 fenetre INCONNUE : kickoff_freeze.json illisible.")
        print("     Sans elle, on ne sait pas quelles entrees comptent — et")
        print("     compter tout le journal melangerait les essais d'avant le")
        print("     kickoff au resultat hors echantillon. On s'arrete.")
        raise SystemExit(2)
    debut, fin = fenetre
    print("  fenetre : %s  ->  %s" % (debut.strftime("%d/%m %H:%M"),
                                      fin.strftime("%d/%m %H:%M")))
    if illisibles:
        print("  ⚠️  %d ligne(s) de journal ILLISIBLES, sautees et comptees ici."
              % illisibles)

    passages = []
    for e in entrees:
        if e.get("run_type") not in (None, "", "agent"):
            continue
        try:
            t = datetime.fromisoformat(str(e.get("timestamp")).replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue
        if debut <= t <= fin:
            passages.append(e)

    # ── 1. LE MECANISME DE REFUS ─────────────────────────────────────────
    refus = Counter()
    refus_par_symbole = Counter()
    retenus = 0
    for e in passages:
        for v in (e.get("verdicts") or []):
            if v.get("tradeable"):
                retenus += 1
                continue
            cat = _categorie(v.get("reason") or "")
            refus[cat] += 1
            if cat == "garde anti-retrospection":
                refus_par_symbole[v.get("symbol")] += 1
    print()
    print("  1. LE MECANISME DE REFUS")
    total_verdicts = retenus + sum(refus.values())
    if not total_verdicts:
        print("     ⬜ aucun verdict dans la fenetre — INCONNU, pas zero.")
    else:
        print("     %d verdict(s) rendus : %d retenu(s), %d refus"
              % (total_verdicts, retenus, sum(refus.values())))
        for cat, n in refus.most_common():
            print("       %-28s %3d  (%.0f %%)"
                  % (cat, n, 100.0 * n / total_verdicts))
        if refus_par_symbole:
            print("     refus par le garde, par symbole :")
            for sym, n in refus_par_symbole.most_common():
                print("       %-8s %d" % (sym, n))

    # ── 2. LA REGULARITE D'EXECUTION ─────────────────────────────────────
    attendus = _passages_attendus(debut, fin)
    print()
    print("  2. LA REGULARITE D'EXECUTION")
    print("     %d passage(s) reel(s) pour %d attendu(s)" % (len(passages), attendus))
    if attendus and len(passages) < attendus:
        print("     🔴 %d passage(s) MANQUANT(S) — un agent qui n'a pas tourne"
              % (attendus - len(passages)))
        print("        n'a rien prouve, ni dans un sens ni dans l'autre.")
    elif attendus:
        print("     🟢 aucun passage manquant.")

    # ── 3. LES ENTREES ───────────────────────────────────────────────────
    issues = Counter()
    for e in passages:
        for t in (e.get("trades") or []):
            issues[t.get("outcome") or "inconnu"] += 1
    print()
    print("  3. LES ENTREES")
    if not issues:
        print("     aucune tentative d'entree dans la fenetre.")
    for k, n in issues.most_common():
        print("     %-24s %d" % (k, n))

    # ── 4. LE P&L, EN DERNIER ET ASSUME ──────────────────────────────────
    print()
    print("  4. LE P&L  (en dernier, deliberement)")
    depart = None
    try:
        with open(ETAT, encoding="utf-8") as fh:
            depart = json.load(fh).get("starting_equity")
    except (OSError, json.JSONDecodeError):
        pass
    if depart:
        print("     equite de depart : %.2f" % depart)
    else:
        print("     ⬜ equite de depart INCONNUE (state.json illisible).")
    if args.reseau:
        try:
            import alpaca_cli
            eq = float(alpaca_cli.get_account().get("equity"))
            print("     equite actuelle  : %.2f" % eq)
            if depart:
                print("     variation        : %+.2f (%+.2f %%)"
                      % (eq - depart, 100.0 * (eq - depart) / depart))
        except Exception as err:
            print("     🔴 equite actuelle NON LUE (%s) — pas zero, inconnue."
                  % type(err).__name__)
    else:
        print("     equite actuelle non demandee (--reseau pour l'interroger).")
    print()
    print("     Sur cinq seances et une poignee de trades, ce chiffre ne")
    print("     distingue pas une strategie d'un tirage. Il est rapporte")
    print("     parce qu'il existe, pas parce qu'il prouve quoi que ce soit.")
    print("=" * 74)


if __name__ == "__main__":
    main()
