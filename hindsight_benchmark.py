#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha
#
# Sous licence MIT, redistribuer ce fichier -- entier ou par morceaux --
# OBLIGE a conserver cet avis. C'est la seule contrainte de la licence, et
# c'est la raison d'etre de ces trois lignes : un fichier copie-colle
# emporte desormais sa provenance avec lui.
"""Caracterisation de `hindsight_guard` sur verite-terrain CONNUE.

POURQUOI CE FICHIER EXISTE
==========================
Les tests existants verifient la LOGIQUE du garde-fou : dependance a l'ordre
des candidats, candidat non notable, frontiere du seuil, NaN. Ils repondent a
« le code fait-il ce qu'il dit ». Ils ne repondent PAS a la question qu'un
quant pose en premier :

    « Pourquoi devrais-je considerer ton test comme une preuve d'absence de
      surapprentissage, plutot que comme une heuristique de stabilite des
      parametres ? »

La reponse honnete est : il ne faut PAS. Le garde-fou ne detecte pas « le
surapprentissage » en general. Il detecte UNE chose precise -- une selection de
parametre qui change quand on retire l'information indisponible au moment de la
decision -- et ce fichier mesure a quel point il le fait, avec quel taux de
fausse alerte, a partir de quelle taille d'effet, et surtout CE QU'IL NE
DETECTE PAS.

Un mecanisme dont on a mesure les limites est plus defendable qu'un mecanisme
dont on affirme qu'il n'en a pas.

POURQUOI LA VERITE-TERRAIN EST CONSTRUITE AU NIVEAU DES SCORES
==============================================================
`check_selection_leakage(candidats, score_fn, seuil)` est generique : son
contrat porte sur des SCORES, pas sur des prix. Fabriquer la fuite au niveau du
score_fn est donc une mesure de son contrat reel, et c'est le seul moyen de
controler EXACTEMENT la taille de l'effet -- ce qui est indispensable pour
tracer une courbe de detection plutot que d'annoncer un chiffre unique.

Limite assumee : ce banc ne demontre donc PAS que le pipeline de prix produit
ces situations-la. C'est une caracterisation du detecteur, pas de la strategie.

LES QUATRE JEUX
===============
A  aucune fuite, edge reel      -> verite : PAS de fuite. Mesure le taux de
                                   FAUSSE ALERTE.
B  fuite evidente               -> verite : fuite. Mesure le taux de detection.
C  fuite subtile, effet balaye  -> verite : fuite. Donne une COURBE de
                                   detection en fonction de la taille d'effet.
D  surapprentissage SANS
   look-ahead (aucun edge)      -> verite : surapprentissage, mais AUCUNE
                                   fuite de selection. Mesure ce que le
                                   garde-fou repond a une situation qu'il
                                   n'est pas concu pour attraper.

Le jeu D est le plus important des quatre : c'est celui qui delimite la
promesse.
"""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

from hindsight_guard import check_selection_leakage

CANDIDATS = [10, 20, 30, 60, 90]

# Seuil de Sharpe. CORRIGE le 28/08/2026 : cette constante valait 0.3 et se
# disait « celui du projet ». Verification faite, le projet utilise 0.0 PARTOUT
# -- agent.py (defaut de --sharpe-threshold), backtest.py, et les deux appels
# de compare_strategies.py. Le chiffre etait invente et l'etiquette fausse.
#
# Ce n'est pas un detail ici : le jeu D mesure precisement QUI protege contre
# une selection sans edge, le garde-fou ou le seuil. Mesurer avec un seuil que
# le projet n'emploie pas rendait ce resultat sans objet -- et c'est le
# resultat que j'avais presente comme le plus important des quatre.
#
# Exactement l'erreur que ce projet existe pour attraper -- un chiffre publie
# qui repose sur une constante que personne n'a verifiee -- commise dans
# l'outil ecrit pour l'auditer.
SEUIL = 0.0

# Bruit d'estimation sur un Sharpe mesure sur un echantillon fini. Les deux
# fenetres (pleine / in-sample) sont notees sur des donnees qui se recouvrent
# largement mais pas completement : leurs bruits sont donc correles, pas
# independants. RHO fixe ce recouvrement.
SIGMA = 0.30
RHO = 0.70

N_ESSAIS = 4000
GRAINE = 20260827

# Les quatre verdicts possibles sont ceux de LeakageReport.verdict_label().
# Ils ne sont PAS recopies dans une constante ici : une liste declaree a
# cote de la vraie regle, jamais lue, ne fait que promettre une
# synchronisation qui n'existe pas. Une `VERDICTS = [...]` morte trainait
# ici -- retiree le 28/08 par le test qui traque justement ca, deux minutes
# apres que le meme test eut attrape une constante morte dans le banc
# jumeau. Les colonnes du rapport nomment les quatre verdicts la ou elles
# les lisent, avec _pct(), donc a un seul endroit.


def _bruits_correles(rng: random.Random) -> Tuple[float, float]:
    """Deux tirages de bruit correles a RHO -- le recouvrement des donnees.

    Sans correlation, la fenetre pleine et la fenetre in-sample seraient deux
    mesures independantes du meme candidat, et le gagnant changerait par pur
    hasard bien plus souvent qu'en realite : le taux de fausse alerte mesure
    serait alors une propriete du banc, pas du garde-fou.
    """
    commun = rng.gauss(0.0, 1.0)
    a = rng.gauss(0.0, 1.0)
    b = rng.gauss(0.0, 1.0)
    f = RHO ** 0.5
    g = (1.0 - RHO) ** 0.5
    return SIGMA * (f * commun + g * a), SIGMA * (f * commun + g * b)


def _essai(moyennes: Dict[int, float], fuite: Dict[int, float],
           rng: random.Random) -> str:
    """Un essai : on note chaque candidat sur les deux fenetres, on demande son
    verdict au garde-fou, on rend le mot-cle.

    `moyennes` = la qualite VRAIE de chaque candidat, identique sur les deux
    fenetres. `fuite` = le bonus qui n'existe QUE sur la fenetre pleine, c'est-
    a-dire l'avantage qu'un candidat ne doit qu'a l'information indisponible au
    moment de la decision. Une fuite est donc, par construction, une entree non
    nulle dans `fuite`.
    """
    scores_pleins: Dict[int, float] = {}
    scores_in: Dict[int, float] = {}
    for c in CANDIDATS:
        bp, bi = _bruits_correles(rng)
        scores_pleins[c] = moyennes[c] + fuite.get(c, 0.0) + bp
        scores_in[c] = moyennes[c] + bi

    rapport = check_selection_leakage(
        CANDIDATS,
        lambda cand, split: (scores_pleins if split == "full" else scores_in)[cand],
        threshold=SEUIL,
    )
    return rapport.verdict_label()


def _campagne(nom: str, moyennes: Dict[int, float], fuite: Dict[int, float],
              graine: int) -> Counter:
    rng = random.Random(graine)
    c = Counter()
    for _ in range(N_ESSAIS):
        c[_essai(moyennes, fuite, rng)] += 1
    return c


def _pct(compte: Counter, cle: str) -> float:
    return 100.0 * compte.get(cle, 0) / max(1, sum(compte.values()))


# ---------------------------------------------------------------------------
# Les quatre jeux
# ---------------------------------------------------------------------------

def jeu_a() -> Counter:
    """A -- edge reel, AUCUNE fuite. La fenetre 30 est veritablement la
    meilleure, sur les deux fenetres. Le garde-fou devrait dire `agrees`.
    Tout autre verdict est une FAUSSE ALERTE."""
    moyennes = {10: 0.35, 20: 0.45, 30: 0.85, 60: 0.40, 90: 0.30}
    return _campagne("A", moyennes, {}, GRAINE + 1)


def jeu_b(delta: float = 1.20) -> Counter:
    """B -- fuite EVIDENTE. La fenetre 90 est mediocre en verite, mais recoit
    un gros bonus qui n'existe que sur la fenetre pleine : elle gagne donc
    l'historique complet sans rien valoir sur l'information connaissable."""
    moyennes = {10: 0.35, 20: 0.45, 30: 0.85, 60: 0.40, 90: 0.30}
    return _campagne("B", moyennes, {90: delta}, GRAINE + 2)


def jeu_c() -> List[Tuple[float, Counter]]:
    """C -- meme construction que B, mais l'effet est BALAYE. Donne la courbe :
    a partir de quelle taille de fuite le garde-fou la voit-il ?"""
    moyennes = {10: 0.35, 20: 0.45, 30: 0.85, 60: 0.40, 90: 0.30}
    sortie = []
    for i, delta in enumerate((0.0, 0.15, 0.30, 0.45, 0.60, 0.80, 1.00, 1.40, 2.00)):
        sortie.append((delta, _campagne("C", moyennes, {90: delta},
                                        GRAINE + 100 + i)))
    return sortie


def jeu_a_balaye() -> List[Tuple[float, Counter]]:
    """A balaye -- le taux de fausse alerte en fonction de l'ECART entre le
    meilleur candidat et son suivant.

    Sans ce balayage, le taux de fausse alerte du jeu A serait un chiffre
    unique dependant d'un choix arbitraire (l'ecart que j'ai mis dans mes
    moyennes). Un chiffre qui depend d'un parametre arbitraire est exactement
    ce que ce projet reproche aux backtests des autres.

    Lecture : quand deux candidats sont statistiquement indiscernables, refuser
    n'est PAS un bug -- c'est la bonne reponse, on ne peut effectivement pas
    dire lequel est meilleur. La courbe donne donc le prix du test, pas son
    erreur.
    """
    sortie = []
    for i, ecart in enumerate((0.0, 0.10, 0.20, 0.30, 0.40, 0.60, 0.80, 1.20)):
        moyennes = {10: 0.35, 20: 0.45, 30: 0.45 + ecart, 60: 0.40, 90: 0.30}
        sortie.append((ecart, _campagne("A-balaye", moyennes, {},
                                        GRAINE + 200 + i)))
    return sortie


def comparaison_a_quatre_symboles() -> Dict[str, float]:
    """« momentum passe 4/4, HV-rank 3/4 » : cet ecart veut-il dire quelque
    chose ?

    Cette phrase est dans le README du projet, sous le titre « Honest fact
    worth surfacing ». L'intention est honnete -- on publie un resultat qui
    dessert la strategie retenue. Mais c'est une comparaison de deux
    proportions a n=4, et personne ne lui avait demande son intervalle.

    Le banc rend la question calculable, donc il faut la poser : lire un signal
    dans un ecart qui tient dans le bruit est EXACTEMENT l'erreur que ce projet
    existe pour attraper. La commettre dans son propre README serait le pire
    endroit possible pour la laisser.
    """
    from math import comb

    # Fisher exact bilateral sur la table observee.
    a, b, c, d = 4, 0, 3, 1

    def hyper(x: int) -> float:
        return comb(a + b, x) * comb(c + d, a + c - x) / comb(a + b + c + d, a + c)

    obs = hyper(a)
    lo, hi = max(0, a + c - (c + d)), min(a + b, a + c)
    fisher = sum(hyper(x) for x in range(lo, hi + 1)
                 if hyper(x) <= obs * (1 + 1e-9))

    # Si les deux strategies etaient IDENTIQUES, a quelle frequence verrait-on
    # un ecart d'au moins un symbole sur quatre ?
    ecarts = {}
    for pp in (0.70, 0.80, 0.85, 0.90, 0.95):
        def bino(k: int, pp: float = pp) -> float:
            return comb(4, k) * pp ** k * (1 - pp) ** (4 - k)
        ecarts[pp] = sum(bino(i) * bino(j)
                         for i in range(5) for j in range(5) if abs(i - j) >= 1)

    return {"fisher": fisher, "ecarts": ecarts}


def jeu_d() -> Counter:
    """D -- LE jeu qui delimite la promesse. Aucun candidat n'a le moindre edge
    (toutes les moyennes vraies sont nulles) et il n'y a AUCUNE fuite : le
    gagnant est designe par le seul bruit. C'est du surapprentissage pur, sans
    look-ahead.

    Le garde-fou n'est PAS concu pour attraper ca. La question mesuree ici
    n'est donc pas « le detecte-t-il » mais « que repond-il », et surtout :
    combien de fois certifie-t-il `agrees` une selection qui ne vaut rien ?
    """
    moyennes = {c: 0.0 for c in CANDIDATS}
    return _campagne("D", moyennes, {}, GRAINE + 3)


def jeu_d_sans_seuil() -> Counter:
    """D bis -- le meme jeu, seuil ramene a zero, pour isoler QUI fait le
    travail. Si `agrees` explose ici alors qu'il etait rare avec le seuil du
    projet, c'est que ce n'est pas le garde-fou qui protege contre une
    selection sans edge : c'est le seuil de Sharpe."""
    global SEUIL
    ancien = SEUIL
    SEUIL = -99.0
    try:
        moyennes = {c: 0.0 for c in CANDIDATS}
        return _campagne("D-bis", moyennes, {}, GRAINE + 3)
    finally:
        SEUIL = ancien


# ---------------------------------------------------------------------------
# Rapport
# ---------------------------------------------------------------------------

def _ligne(nom: str, compte: Counter) -> str:
    return "| %s | %.1f%% | %.1f%% | %.1f%% | %.1f%% |" % (
        nom,
        _pct(compte, "agrees"),
        _pct(compte, "LEAK DETECTED"),
        _pct(compte, "NO EDGE"),
        _pct(compte, "CANNOT CONCLUDE"),
    )


def construire_rapport() -> str:
    a = jeu_a()
    b = jeu_b()
    c = jeu_c()
    d = jeu_d()
    ab = jeu_a_balaye()
    cmp4 = comparaison_a_quatre_symboles()
    d2 = jeu_d_sans_seuil()

    faux_positifs = 100.0 - _pct(a, "agrees")
    detection_b = _pct(b, "LEAK DETECTED")

    seuil_detecte = None
    for delta, compte in c:
        if _pct(compte, "LEAK DETECTED") >= 50.0:
            seuil_detecte = delta
            break

    L = []
    L.append("# hindsight_guard — caractérisation sur vérité-terrain connue")
    L.append("")
    L.append("*Généré par `hindsight_benchmark.py`. %d essais par condition, "
             "graine fixe (%d) — reproductible à l'identique.*"
             % (N_ESSAIS, GRAINE))
    L.append("")
    L.append("Ce banc ne mesure pas si la stratégie gagne de l'argent. Il mesure "
             "**ce que le détecteur détecte**, avec quel taux de fausse alerte, "
             "à partir de quelle taille d'effet, et surtout **ce qu'il ne "
             "détecte pas**.")
    L.append("")
    L.append("Paramètres : seuil de Sharpe **%.2f**, bruit d'estimation σ=**%.2f**, "
             "corrélation des deux fenêtres ρ=**%.2f** (elles sont notées sur "
             "des données qui se recouvrent — les traiter comme indépendantes "
             "gonflerait artificiellement le taux de fausse alerte)."
             % (SEUIL, SIGMA, RHO))
    L.append("")
    L.append("## Les quatre jeux")
    L.append("")
    L.append("| jeu | vérité-terrain | `agrees` | `LEAK DETECTED` | `NO EDGE` | `CANNOT CONCLUDE` |")
    L.append("|---|---|---|---|---|---|")
    L.append(_ligne("**A** — edge réel, aucune fuite | *pas de fuite*", a))
    L.append(_ligne("**B** — fuite évidente (δ=1.20) | *fuite*", b))
    L.append(_ligne("**D** — aucun edge, aucune fuite | *surapprentissage seul*", d))
    L.append(_ligne("**D-bis** — idem, seuil neutralisé | *surapprentissage seul*", d2))
    L.append("")
    L.append("## Ce que ces chiffres disent")
    L.append("")
    L.append("**Taux de fausse alerte : %.1f%%** (jeu A). Sur une sélection "
             "réellement stable, le garde-fou se trompe dans %.1f%% des cas — "
             "il refuse de valider une stratégie qui n'avait rien à se "
             "reprocher. Ce n'est pas gratuit : chaque fausse alerte est un "
             "trade non pris." % (faux_positifs, faux_positifs))
    L.append("")
    L.append("**Taux de détection sur fuite franche : %.1f%%** (jeu B)."
             % detection_b)
    L.append("")
    if seuil_detecte is not None:
        L.append("**Seuil de sensibilité : δ ≈ %.2f.** En dessous, la fuite passe "
                 "plus d'une fois sur deux. C'est la limite honnête du "
                 "mécanisme — une fuite plus petite que le bruit "
                 "d'estimation n'est pas distinguable du bruit, et aucun test "
                 "à échantillon fini ne peut faire mieux." % seuil_detecte)
    else:
        L.append("**Aucune taille d'effet balayée n'atteint 50 % de détection** — "
                 "à relire avant de publier ce chiffre.")
    L.append("")
    L.append("### Le jeu D est le plus important")
    L.append("")
    L.append("Aucun candidat n'a d'edge, et il n'y a **aucune fuite** : le "
             "gagnant est désigné par le seul bruit. C'est du surapprentissage "
             "pur, sans look-ahead — précisément ce que le garde-fou **n'est "
             "pas conçu pour attraper**.")
    L.append("")
    L.append("Avec le seuil du projet, il certifie `agrees` dans **%.1f%%** des "
             "cas. Seuil neutralisé, ce chiffre monte à **%.1f%%**."
             % (_pct(d, "agrees"), _pct(d2, "agrees")))
    L.append("")
    ecart_du_seuil = _pct(d2, "agrees") - _pct(d, "agrees")
    L.append("**Avec le seuil réellement utilisé par ce projet — 0.0 — le seuil "
             "ne protège de rien : le neutraliser complètement ne déplace le "
             "chiffre que de %.1f point.** Sur une sélection sans le moindre "
             "edge, rien dans la chaîne ne s'y oppose : ni le garde-fou, qui "
             "n'est pas conçu pour ça et le dit, ni le seuil, qui est à zéro."
             % ecart_du_seuil)
    L.append("")
    L.append("*Correction du 28/08/2026, et elle porte sur ce même paragraphe.* "
             "Une première version de ce banc employait un seuil de **0.3** en "
             "le présentant comme « celui du projet ». Vérification faite, le "
             "projet utilise **0.0** partout — `agent.py`, `backtest.py`, et "
             "les deux appels de `compare_strategies.py`. Avec le faux seuil, "
             "`NO EDGE` couvrait 27.4 % des cas et la conclusion publiée ici "
             "était que « c'est le seuil de Sharpe qui protège ». C'était faux, "
             "et faux parce que la mesure reposait sur une constante que "
             "personne n'avait vérifiée — exactement l'erreur que ce projet "
             "existe pour attraper, commise dans l'outil écrit pour l'auditer.")
    L.append("")
    L.append("Ce que la correction change, en clair : le résultat est **plus "
             "sévère**, pas moins. Le garde-fou certifie une sélection sans "
             "valeur une fois sur deux, et aucun autre mécanisme ne rattrape "
             "ça. C'est un argument mesuré en faveur d'un seuil de Sharpe non "
             "nul — décision de méthode qui appartient à l'opérateur, pas une "
             "modification à faire en douce à huit jours du rendu.")
    L.append("")
    L.append("## Courbe de détection (jeu C)")
    L.append("")
    L.append("| taille de fuite δ | `LEAK DETECTED` | `agrees` | `NO EDGE` |")
    L.append("|---|---|---|---|")
    for delta, compte in c:
        L.append("| %.2f | %.1f%% | %.1f%% | %.1f%% |"
                 % (delta, _pct(compte, "LEAK DETECTED"),
                    _pct(compte, "agrees"), _pct(compte, "NO EDGE")))
    L.append("")
    L.append("À δ=0 il n'y a **pas** de fuite : la ligne δ=0.00 est donc un "
             "second témoin du taux de fausse alerte, obtenu par un chemin "
             "différent du jeu A.")
    L.append("")
    L.append("## Le taux de fausse alerte n'est pas un chiffre, c'est une courbe")
    L.append("")
    L.append("Le %.1f%% du jeu A dépend de l'écart que j'ai mis entre le "
             "meilleur candidat et son suivant. Un chiffre qui dépend d'un "
             "paramètre arbitraire est exactement ce que ce projet reproche aux "
             "backtests des autres — voici donc l'écart balayé, à bruit "
             "constant (σ=%.2f)." % (faux_positifs, SIGMA))
    L.append("")
    L.append("| écart réel meilleur − suivant | fausse alerte | `agrees` |")
    L.append("|---|---|---|")
    for ecart, compte in ab:
        L.append("| %.2f | %.1f%% | %.1f%% |"
                 % (ecart, 100.0 - _pct(compte, "agrees"), _pct(compte, "agrees")))
    L.append("")
    L.append("**Ce n'est pas un bug, c'est le prix du test.** Quand deux "
             "candidats sont statistiquement indiscernables, refuser est la "
             "bonne réponse : on ne *peut* pas dire lequel est meilleur. La "
             "courbe dit simplement à partir de quelle séparation réelle le "
             "garde-fou cesse de payer ce prix.")
    L.append("")
    L.append("## Une réserve sur le mot « LEAK »")
    L.append("")
    L.append("Dans le jeu D il n'y a **aucune fuite** — et le garde-fou "
             "imprime pourtant `LEAK DETECTED` dans %.1f%% des cas. Ce qu'il "
             "mesure réellement, c'est l'**instabilité du gagnant entre les "
             "deux fenêtres**. Une fuite en est la cause la plus intéressante, "
             "pas la seule : le bruit d'estimation produit la même signature."
             % _pct(d, "LEAK DETECTED"))
    L.append("")
    L.append("C'est une limite de vocabulaire, pas de code, et elle est "
             "assumée ici plutôt que corrigée en silence.")
    L.append("")
    L.append("## Le banc retourné contre le projet lui-même")
    L.append("")
    L.append("Le README affirme, sous le titre *« Honest fact worth "
             "surfacing »*, que `momentum_strategy.py` passe le garde-fou sur "
             "**4 symboles sur 4** tandis que `vol_strategy.py` n'en passe que "
             "**3 sur 4**. L'intention est honnête — c'est un résultat qui "
             "dessert la stratégie retenue. Mais personne n'avait demandé son "
             "intervalle à cette comparaison.")
    L.append("")
    L.append("- Test exact de Fisher sur la table observée (4/0 contre 3/1) : "
             "**p = %.3f**." % cmp4["fisher"])
    L.append("- Si les deux stratégies étaient **identiques**, un écart d'au "
             "moins un symbole apparaîtrait quand même :")
    L.append("")
    L.append("| taux de succès réel par symbole | écart ≥ 1 symbole observé |")
    L.append("|---|---|")
    for pp, v in sorted(cmp4["ecarts"].items()):
        L.append("| %.2f | %.1f%% |" % (pp, 100.0 * v))
    L.append("")
    L.append("**« Momentum est plus propre sur le test de fuite » est donc un "
             "tirage à pile ou face présenté comme un constat.** Le fait mérite "
             "d'être publié ; la comparaison ne mérite pas qu'on agisse dessus. "
             "Lire un signal dans un écart qui tient dans le bruit est "
             "exactement l'erreur que ce projet existe pour attraper — et il "
             "l'avait commise dans son propre README. C'est corrigé là-bas, "
             "avec ces chiffres.")
    L.append("")
    L.append("## Ce que ce banc ne démontre pas")
    L.append("")
    L.append("- La vérité-terrain est construite **au niveau des scores**, pas "
             "des prix. C'est le contrat réel de `check_selection_leakage`, et "
             "c'est le seul moyen de contrôler exactement la taille d'effet — "
             "mais cela ne démontre pas que le pipeline de prix produit ces "
             "situations-là.")
    L.append("- Le bruit est gaussien et homoscédastique. Les vrais Sharpe "
             "d'échantillon ne le sont pas.")
    L.append("- Cinq candidats, une seule fuite injectée à la fois. Pas de "
             "correction pour tests multiples.")
    L.append("")
    L.append("**Formulation défendable de la promesse, compte tenu de ces "
             "mesures :** *Hindsight tests whether a model's parameter "
             "selection remains stable when information unavailable at decision "
             "time is removed.* Ni plus, ni moins.")
    L.append("")
    return "\n".join(L)


def main() -> None:
    rapport = construire_rapport()
    Path(__file__).parent.joinpath("HINDSIGHT_BENCHMARK.md").write_text(
        rapport, encoding="utf-8")
    print(rapport)


if __name__ == "__main__":
    main()
