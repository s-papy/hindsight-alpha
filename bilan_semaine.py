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
import math
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


def _lire_journal() -> "tuple[list | None, int]":
    """Une ligne illisible est SAUTEE, pas fatale -- meme choix que partout
    ailleurs dans ce depot. Mais on COMPTE les sautees et on le dit : un
    bilan qui ignore silencieusement une partie de ses donnees n'est pas un
    bilan.

    Rend `(None, 0)` si le journal ne s'ouvre pas DU TOUT -- ce n'est pas
    « zero ligne », c'est « je n'ai pas pu lire ». L'appelant s'arrete.

    CE QUE RENDAIT CETTE FONCTION AVANT le 29/08/2026 : `([], -1)`. Le -1
    partait tel quel dans le rapport public (« unreadable log lines skipped:
    -1 ») et, pire, la liste vide faisait conclure a la section 2 :

        0 actual run(s) for 1 expected
        🔴 1 run(s) MISSING — an agent that did not run proved nothing

    ...avec un code de sortie 0. Une ACCUSATION contre l'agent, produite par
    l'incapacite a lire un fichier. Dans le meme rapport, la section 1 disait
    correctement « ⬜ no verdict — UNKNOWN, not zero » : la meme absence,
    lue de deux facons opposees, a quatre lignes d'intervalle.

    Le fichier de gel, l'autre entree de ce script, avait DEJA ce traitement
    -- illisible, on s'arrete. La regle etait ecrite pour un jumeau et pas
    pour l'autre.

    Un journal VIDE (le fichier existe, zero ligne) reste `([], 0)` : la
    lecture a reussi, et « 0 passage » est alors une mesure, pas une
    ignorance."""
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
        return None, 0
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
        return "hindsight guard"
    if re.search(r"volatility not cheap|regime", motif, re.I):
        return "volatility regime"
    return "other"


def main() -> None:
    # `description=__doc__` DEVERSAIT LA DOCSTRING FRANCAISE dans --help,
    # reflowee par argparse -- donc la liste numerotee de l'ordre, qui est
    # tout l'engagement, sortait en un pave illisible. Et LIVE_WEEK.md, en
    # anglais, envoie le lecteur ici. La docstring reste en francais comme
    # tout le commentaire du depot ; ce qui S'IMPRIME est en anglais.
    p = argparse.ArgumentParser(
        description="Counts what the live week actually did. It does not "
                    "write prose, and it changes nothing.",
        epilog="Reported in this order, fixed before the results were known "
               "(see LIVE_WEEK.md):\n"
               "  1. the refusal mechanism  -- how often the hindsight guard "
               "refused a symbol, and which\n"
               "  2. execution regularity   -- expected runs vs actual runs\n"
               "  3. entries                -- orders submitted\n"
               "  4. P&L                    -- last, and owned as such\n\n"
               "The window comes from kickoff_freeze.json. If it cannot be "
               "read, this script stops\ninstead of counting the whole log: "
               "\"I don't know which entries count\" must never\nbecome "
               "\"I count them all\".",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--reseau", action="store_true",
                   help="query Alpaca for the real current equity")
    args = p.parse_args()

    entrees, illisibles = _lire_journal()
    fenetre = _fenetre()

    print()
    print("=" * 74)
    print("LIVE WEEK REPORT — %s" % datetime.now().strftime("%d/%m/%Y %H:%M"))
    print("=" * 74)

    if fenetre is None:
        print("  🔴 WINDOW UNKNOWN: kickoff_freeze.json could not be read.")
        print("     Without it there is no way to tell which entries count — and")
        print("     counting the whole log would mix the pre-kickoff development")
        print("     runs into the out-of-sample result. Stopping here.")
        raise SystemExit(2)
    debut, fin = fenetre
    print("  window: %s  ->  %s" % (debut.strftime("%d/%m %H:%M"),
                                    fin.strftime("%d/%m %H:%M")))
    if entrees is None:
        print("  🔴 LOG UNREADABLE: decision_log.jsonl could not be opened.")
        print("     Every figure below would be built on no data — and the")
        print("     execution-regularity section would report the agent as")
        print("     MISSING every run it cannot see. That is an accusation")
        print("     produced by a failure to read a file, not a measurement.")
        print("     Stopping here, for the same reason as an unreadable window.")
        raise SystemExit(2)

    # TOUJOURS imprime, meme a zero. LIVE_WEEK.md promet publiquement que les
    # lignes illisibles sont « skipped AND COUNTED IN THE OUTPUT » ; se taire a
    # zero rendait cette phrase vraie seulement quand il y en avait. Un lecteur
    # ne pouvait pas distinguer « aucune » de « pas verifie ».
    print("  unreadable log lines skipped: %d" % illisibles)

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
            if cat == "hindsight guard":
                refus_par_symbole[v.get("symbol")] += 1
    print()
    print("  1. THE REFUSAL MECHANISM")
    total_verdicts = retenus + sum(refus.values())
    if not total_verdicts:
        print("     ⬜ no verdict inside the window — UNKNOWN, not zero.")
    else:
        print("     %d verdict(s): %d tradeable, %d refused"
              % (total_verdicts, retenus, sum(refus.values())))
        # LE DENOMINATEUR EST NOMME. Il est le total des verdicts, retenus
        # compris -- les pourcentages des refus ne font donc pas 100 %, et
        # sous un titre « refused » un lecteur les sommait pour trouver 75 %.
        # Un pourcentage sans sa base est une invitation a se tromper.
        for cat, n in refus.most_common():
            print("       %-28s %3d  (%.0f %% of all verdicts)"
                  % (cat, n, 100.0 * n / total_verdicts))
        if refus_par_symbole:
            print("     refused by the hindsight guard, per symbol:")
            for sym, n in refus_par_symbole.most_common():
                print("       %-8s %d" % (sym, n))

    # ── 2. LA REGULARITE D'EXECUTION ─────────────────────────────────────
    attendus = _passages_attendus(debut, fin)
    print()
    print("  2. EXECUTION REGULARITY")
    print("     %d actual run(s) for %d expected" % (len(passages), attendus))
    if attendus and len(passages) < attendus:
        print("     🔴 %d run(s) MISSING — an agent that did not run proved"
              % (attendus - len(passages)))
        print("        nothing, in either direction.")
    elif attendus:
        print("     🟢 no missing run.")

    # ── 3. LES ENTREES ───────────────────────────────────────────────────
    issues = Counter()
    for e in passages:
        for t in (e.get("trades") or []):
            issues[t.get("outcome") or "unknown"] += 1
    print()
    print("  3. ENTRIES")
    if not issues:
        print("     no entry attempted inside the window.")
    for k, n in issues.most_common():
        print("     %-24s %d" % (k, n))

    # ── 4. LE P&L, EN DERNIER ET ASSUME ──────────────────────────────────
    print()
    print("  4. P&L  (last, deliberately)")
    # LE MESSAGE NE NOMME PLUS UNE CAUSE QU'IL N'A PAS MESUREE.
    #
    # C'etait `except (OSError, JSONDecodeError): pass` puis `if depart:`,
    # avec un seul texte : « starting equity UNKNOWN (state.json unreadable) ».
    # Mesure le 29/08/2026, trois situations differentes, message identique :
    #
    #   state.json LISIBLE sans le champ   -> « unreadable »  (faux)
    #   starting_equity = 0.0              -> « unreadable »  (doublement
    #                                          faux : lisible, present, et
    #                                          une valeur)
    #   fichier vraiment absent            -> « unreadable »  (enfin vrai)
    #
    # Et le cas 0.0 est precisement la ligne de base corrompue que
    # risk_gates._record_starting_equity a appris a REFUSER le 28/08. Si elle
    # arrivait quand meme ici, le rapport accusait le fichier au lieu de
    # montrer la valeur aberrante.
    depart, cause = None, None
    try:
        with open(ETAT, encoding="utf-8") as fh:
            brut = json.load(fh).get("starting_equity")
    except OSError as err:
        cause = "state.json could not be opened (%s)" % type(err).__name__
    except (ValueError, json.JSONDecodeError):
        cause = "state.json is not readable JSON"
    else:
        if brut is None:
            cause = "state.json carries no starting_equity yet"
        elif isinstance(brut, bool) or not isinstance(brut, (int, float)):
            cause = ("state.json records a starting equity that is not a "
                     "number (%r)" % (brut,))
        elif not math.isfinite(brut):
            cause = ("state.json records a starting equity that is not "
                     "finite (%r)" % (brut,))
        elif brut <= 0:
            # PAS « inconnu » : c'est une valeur, et elle est aberrante. La
            # montrer est le seul moyen de la faire corriger.
            cause = ("state.json records a starting equity of %r — risk_gates "
                     "refuses to record such a baseline, so this one predates "
                     "that guard or was written by something else" % (brut,))
        else:
            depart = float(brut)
    if depart is not None:
        print("     starting equity : %.2f" % depart)
    else:
        print("     ⬜ starting equity UNKNOWN — %s." % cause)
    if args.reseau:
        try:
            import alpaca_cli
            eq = float(alpaca_cli.get_account().get("equity"))
            print("     current equity  : %.2f" % eq)
            if depart is not None:
                print("     change          : %+.2f (%+.2f %%)"
                      % (eq - depart, 100.0 * (eq - depart) / depart))
        except Exception as err:
            print("     🔴 current equity NOT READ (%s) — not zero, unknown."
                  % type(err).__name__)
    else:
        print("     current equity not requested (--reseau to query it).")
    print()
    print("     Over five sessions and a handful of trades, this figure does")
    print("     not separate a strategy from a coin flip. It is reported")
    print("     because it exists, not because it proves anything.")
    print("=" * 74)


if __name__ == "__main__":
    main()
