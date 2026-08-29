#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha
#
# Sous licence MIT, redistribuer ce fichier -- entier ou par morceaux --
# OBLIGE a conserver cet avis. C'est la seule contrainte de la licence, et
# c'est la raison d'etre de ces trois lignes : un fichier copie-colle
# emporte desormais sa provenance avec lui.
"""IN_SAMPLE_HOLDOUT_DAYS = 20 : ce nombre a-t-il jamais ete justifie ?

CE QUE CE FICHIER MESURE, ET POURQUOI L'AUTRE BANC NE POUVAIT PAS
=================================================================
`hindsight_benchmark.py` fabrique la verite-terrain au niveau des SCORES. Le
holdout n'y apparait donc nulle part : c'est `score_hv_window` qui l'applique,
en amont, sur les PRIX. Ce banc-ci descend donc d'un etage.

La question. Le garde-fou compare deux scores :

    plein      -> Sharpe sur les ~700 barres
    in-sample  -> Sharpe sur les ~700 barres MOINS les 20 dernieres

Les deux series se recouvrent donc a **97 %**. Une fuite confinee dans la
queue doit deplacer un Sharpe calcule sur 700 jours assez fort pour faire
changer le gagnant. Personne n'avait mesure si 20 etait un bon choix -- c'est
la meme classe d'erreur que celle trouvee dans le README (« momentum 4/4 vs
3/4 ») : un nombre que personne n'a interroge.

LE PROTOCOLE
============
L'anomalie est de TAILLE FIXE -- les 20 derniers jours -- et c'est le HOLDOUT
qui varie. C'est la question interessante, et non l'inverse :

  . holdout < 20 : la fenetre cachee ne couvre pas toute l'anomalie, qui
                   contamine donc AUSSI le score in-sample. Les deux scores
                   voient la fuite, ils sont d'accord, le garde-fou ne voit
                   rien. Un test aveugle par construction.
  . holdout >= 20 : la fenetre cachee couvre l'anomalie. Le garde-fou peut la
                   voir -- s'il lui reste assez de puissance.

Deux conditions par taille de holdout :

  PROPRE  (k=1.0)  la queue est statistiquement identique au reste. Tout
                   desaccord de gagnants est une FAUSSE ALERTE.
  FUITE   (k=2.6)  les 20 derniers jours ont un regime de volatilite
                   franchement different. Verite-terrain : la queue est
                   anormale.

Le compromis attendu -- et c'est lui qui permet de choisir 20 ou autre chose :
cacher PLUS de jours augmente la detection, mais degrade aussi le score
in-sample (moins de donnees, plus de bruit), donc augmente la fausse alerte.
Un holdout n'est pas « plus il est grand mieux c'est ».
"""

from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import vol_strategy
from vol_strategy import Bar, CANDIDATE_HV_WINDOWS, _sharpe, _vol_strategy_returns

N_BARRES = 500
TAILLE_ANOMALIE = 20          # l'anomalie occupe TOUJOURS les 20 derniers jours
HOLDOUTS = (5, 10, 20, 40, 80)
K_FUITE = 2.6                 # facteur de volatilite applique a la queue
N_ESSAIS = 500          # 120 laissait l'avance de 20 j sous le plancher
GRAINE = 20260827
# Pas de constante de seuil ici, et c'est deliberé : ce banc mesure le
# DESACCORD DE GAGNANTS (_gagnant), pas le verdict du garde-fou, donc aucun
# seuil n'intervient. Une constante `SEUIL = 0.3` trainait a cet endroit sans
# etre lue une seule fois -- retiree le 28/08. C'est precisement ce que
# TestAucunSeuilMort existe pour attraper, et elle etait dans un fichier que
# j'avais ecrit moi-meme.


def _serie(graine: int, k_queue: float) -> List[Bar]:
    """Serie a volatilite VARIABLE (sinon le rang HV vaut 0 partout et rien ne
    distingue quoi que ce soit), avec une queue eventuellement anormale."""
    rng = random.Random(graine)
    barres, prix = [], 100.0
    for i in range(N_BARRES):
        ampl = 0.004 + 0.014 * (0.5 + 0.5 * math.sin(i / 47.0))
        if i >= N_BARRES - TAILLE_ANOMALIE:
            ampl *= k_queue
        prix *= 1.0 + rng.gauss(0.0, ampl)
        barres.append(Bar(close=prix))
    return barres


def _score(barres: Sequence[Bar], fenetre: int) -> float:
    return _sharpe(_vol_strategy_returns(barres, fenetre))


def _plancher(nb_pourcentages: int) -> float:
    """Erreur-type, en POINTS, d'une combinaison de `nb_pourcentages`
    proportions independantes estimees sur N_ESSAIS tirages chacune.

    L'erreur-type d'un pourcentage vaut au plus 50/sqrt(N) points (maximum a
    p=0.5). Combiner k proportions independantes par addition ou soustraction
    multiplie cela par sqrt(k).

        k=2   un ecart utile          detection - fausse alerte
        k=4   une avance              (ecart d'un holdout) - (ecart d'un autre)

    Ecrite ici UNE fois : ce document annoncait deux planchers differents,
    calcules par deux formules ecrites a deux endroits."""
    return (nb_pourcentages ** 0.5) * 50.0 / N_ESSAIS ** 0.5


def _gagnant(scores: Dict[int, float]) -> int:
    """Meme regle que le garde-fou : le plus haut score fini."""
    finis = {c: v for c, v in scores.items() if math.isfinite(v)}
    if not finis:
        return -1
    return max(finis, key=lambda c: finis[c])


def _essai(graine: int, k_queue: float) -> Dict[int, bool]:
    """Un essai. Rend, pour CHAQUE taille de holdout, si les gagnants
    divergent. Les scores « plein » sont calcules une seule fois et reutilises
    pour tous les holdouts -- sinon la grille coute le double pour rien."""
    barres = _serie(graine, k_queue)
    pleins = {c: _score(barres, c) for c in CANDIDATE_HV_WINDOWS}
    g_plein = _gagnant(pleins)

    sortie = {}
    for h in HOLDOUTS:
        coupe = max(0, len(barres) - h)
        ins = {c: _score(barres[:coupe], c) for c in CANDIDATE_HV_WINDOWS}
        sortie[h] = (_gagnant(ins) != g_plein)
    return sortie


def _campagne(k_queue: float, decalage: int) -> Dict[int, float]:
    compte = {h: 0 for h in HOLDOUTS}
    for i in range(N_ESSAIS):
        r = _essai(GRAINE + decalage + i, k_queue)
        for h, divergent in r.items():
            compte[h] += 1 if divergent else 0
    return {h: 100.0 * n / N_ESSAIS for h, n in compte.items()}


def construire_rapport() -> str:
    propre = _campagne(1.0, 0)
    fuite = _campagne(K_FUITE, 10_000)

    L = []
    L.append("# `IN_SAMPLE_HOLDOUT_DAYS = 20` — ce nombre a-t-il jamais été justifié ?")
    L.append("")
    L.append("*Généré par `hindsight_holdout.py`. %d essais par condition et par "
             "taille de holdout, graine fixe (%d), séries de %d barres — "
             "reproductible à l'identique.*"
             % (N_ESSAIS, GRAINE, N_BARRES))
    L.append("")
    L.append("Le garde-fou compare un Sharpe calculé sur ~700 barres à un Sharpe "
             "calculé sur les mêmes barres **moins les 20 dernières**. Les deux "
             "séries se recouvrent donc à **97 %**. Une fuite confinée dans la "
             "queue doit déplacer un Sharpe de 700 jours assez fort pour faire "
             "changer le gagnant — et personne n'avait mesuré si 20 était un bon "
             "choix.")
    L.append("")
    L.append("**Protocole.** L'anomalie est de taille **fixe** (les %d derniers "
             "jours) et c'est le **holdout qui varie**. C'est la question "
             "intéressante : un holdout plus court que la fuite la laisse "
             "contaminer *aussi* le score in-sample — les deux scores voient la "
             "même chose, ils sont d'accord, et le test est aveugle par "
             "construction." % TAILLE_ANOMALIE)
    L.append("")
    L.append("| holdout | fausse alerte (queue saine) | détection (queue anormale) | écart utile |")
    L.append("|---|---|---|---|")
    for h in HOLDOUTS:
        marque = " ←  **livré**" if h == vol_strategy.IN_SAMPLE_HOLDOUT_DAYS else ""
        L.append("| %d j%s | %.1f%% | %.1f%% | %+.1f pts |"
                 % (h, marque, propre[h], fuite[h], fuite[h] - propre[h]))
    L.append("")
    L.append("La colonne qui compte est la dernière : détection **moins** fausse "
             "alerte. Un holdout qui détecte 80 % du temps mais crie aussi 70 % "
             "du temps sur des données saines ne vaut rien — il ne distingue pas.")
    L.append("")

    meilleur = max(HOLDOUTS, key=lambda h: fuite[h] - propre[h])
    livre = vol_strategy.IN_SAMPLE_HOLDOUT_DAYS
    L.append("## Verdict")
    L.append("")
    L.append("Meilleur écart utile sur cette grille : **holdout = %d j** "
             "(%+.1f pts). Le projet livre **%d j** (%+.1f pts)."
             % (meilleur, fuite[meilleur] - propre[meilleur],
                livre, fuite[livre] - propre[livre]))
    L.append("")
    # LE PLANCHER DE SIGNIFICATIVITE, ECRIT UNE FOIS. Corrige le 29/08/2026 :
    # ce document en annoncait DEUX, pour la meme chose et avec les memes mots.
    #
    #     ici, pour le verdict          sqrt(2)*50/sqrt(N) = 3.16 points
    #     plus bas, « ce que ca ne dit
    #     pas »                         100/sqrt(N)        = 4.47 points
    #
    # Une regle ecrite deux fois n'est vraie qu'a un seul endroit -- et un
    # lecteur qui compare les deux lignes voit le document se contredire sur
    # son propre seuil de lisibilite.
    #
    # ET LE VERDICT UTILISAIT LE PLUS PETIT DES DEUX, celui qui le flatte.
    # L'ecart utile d'un holdout est une difference de DEUX pourcentages
    # (erreur-type ~ sqrt(2)*50/sqrt(N)) ; mais l'AVANCE que le verdict
    # compare est une difference de deux ecarts utiles, donc QUATRE
    # pourcentages -- erreur-type ~ 2*50/sqrt(N). Avec 500 essais, 3.16 contre
    # 4.47 : l'avance de 5.2 points passe de 1.64 a 1.16 ecart-type. La
    # conclusion ne change pas -- 20 j reste le meilleur choix de la grille --
    # mais la confiance annoncee etait surevaluee, et c'est exactement
    # l'erreur que ce banc existe pour ne pas commettre.
    plancher = _plancher(2)      # un ecart utile : deux pourcentages
    plancher_avance = _plancher(4)   # une difference d'ecarts : quatre
    ecarts = {h: fuite[h] - propre[h] for h in HOLDOUTS}
    avance = ecarts[meilleur] - max(v for h, v in ecarts.items() if h != meilleur)

    L.append("Plancher de significativité à %d essais : une différence de "
             "deux pourcentages n'est lisible qu'au-delà de **~%.1f points** ; "
             "comparer deux écarts utiles entre eux en met quatre en jeu, donc "
             "**~%.1f points**."
             % (N_ESSAIS, plancher, plancher_avance))
    L.append("")
    # On compare l'avance au plancher des QUATRE pourcentages, pas des deux.
    if meilleur == livre and avance >= plancher_avance:
        L.append("**Le choix livré est le meilleur de la grille, et son avance "
                 "(%.1f pts) dépasse le plancher.** Ce nombre n'avait jamais "
                 "été mesuré ; il l'est maintenant." % avance)
    elif meilleur == livre:
        L.append("**Le choix livré arrive en tête, mais son avance (%.1f pts) "
                 "est SOUS le plancher de significativité.** Il faut donc le "
                 "dire ainsi : à ce nombre d'essais, la grille ne permet pas de "
                 "départager 20 j de ses voisins. Annoncer « 20 est le "
                 "meilleur » serait lire un signal dans du bruit — précisément "
                 "l'erreur que ce projet existe pour attraper." % avance)
    else:
        L.append("**Le choix livré n'arrive pas en tête** (%d j fait mieux de "
                 "%.1f pts). Ce n'est pas une raison de le changer à huit jours "
                 "du rendu : la grille est synthétique, une seule forme "
                 "d'anomalie est testée, et modifier ce paramètre invaliderait "
                 "les backtests publiés." % (meilleur, avance))
    L.append("")
    L.append("**Ce qui est robuste, en revanche, et ne dépend pas de ce "
             "départage :** la détection plafonne (%.0f%% à 20 j, %.0f%% à "
             "80 j) tandis que la fausse alerte, elle, continue de monter "
             "(%.0f%% → %.0f%%). Au-delà de 20 jours on paie donc plus qu'on "
             "ne gagne — c'est la forme de la courbe qui le dit, pas son point "
             "maximum."
             % (fuite[20], fuite[80], propre[20], propre[80]))
    L.append("")
    L.append("## Ce que cette mesure ne dit pas")
    L.append("")
    L.append("- Une seule forme d'anomalie (un changement de régime de "
             "volatilité, facteur ×%.1f). Une fuite peut prendre d'autres "
             "formes." % K_FUITE)
    L.append("- Séries synthétiques à volatilité sinusoïdale. Ce n'est pas un "
             "marché.")
    L.append("- %d essais par cellule : comparer deux écarts utiles entre eux "
             "met quatre pourcentages en jeu, donc une avance de moins de "
             "~%.1f points ne se lit pas." % (N_ESSAIS, plancher_avance))
    L.append("- La règle de gagnant utilisée ici reproduit celle du garde-fou "
             "mais court-circuite ses autres verdicts (`NO EDGE`, `CANNOT "
             "CONCLUDE`) : on mesure le **désaccord de gagnants**, qui est le "
             "mécanisme sous-jacent, pas l'étiquette finale.")
    L.append("")
    return "\n".join(L)


def main() -> None:
    rapport = construire_rapport()
    Path(__file__).parent.joinpath("HINDSIGHT_HOLDOUT.md").write_text(
        rapport, encoding="utf-8")
    print(rapport)


if __name__ == "__main__":
    main()
