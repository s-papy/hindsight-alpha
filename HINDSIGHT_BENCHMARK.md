# hindsight_guard — caractérisation sur vérité-terrain connue

*Généré par `hindsight_benchmark.py`. 4000 essais par condition, graine fixe (20260827) — reproductible à l'identique.*

Ce banc ne mesure pas si la stratégie gagne de l'argent. Il mesure **ce que le détecteur détecte**, avec quel taux de fausse alerte, à partir de quelle taille d'effet, et surtout **ce qu'il ne détecte pas**.

Paramètres : seuil de Sharpe **0.00**, bruit d'estimation σ=**0.30**, corrélation des deux fenêtres ρ=**0.70** (elles sont notées sur des données qui se recouvrent — les traiter comme indépendantes gonflerait artificiellement le taux de fausse alerte).

## Les quatre jeux

| jeu | vérité-terrain | `agrees` | `LEAK DETECTED` | `NO EDGE` | `CANNOT CONCLUDE` |
|---|---|---|---|---|---|
| **A** — edge réel, aucune fuite | *pas de fuite* | 69.8% | 30.2% | 0.0% | 0.0% |
| **B** — fuite évidente (δ=1.20) | *fuite* | 11.8% | 88.2% | 0.0% | 0.0% |
| **D** — aucun edge, aucune fuite | *surapprentissage seul* | 52.0% | 47.4% | 0.6% | 0.0% |
| **D-bis** — idem, seuil neutralisé | *surapprentissage seul* | 53.0% | 47.0% | 0.0% | 0.0% |

## Ce que ces chiffres disent

**Taux de fausse alerte : 30.2%** (jeu A). Sur une sélection réellement stable, le garde-fou se trompe dans 30.2% des cas — il refuse de valider une stratégie qui n'avait rien à se reprocher. Ce n'est pas gratuit : chaque fausse alerte est un trade non pris.

**Taux de détection sur fuite franche : 88.2%** (jeu B).

**Seuil de sensibilité : δ ≈ 0.60.** En dessous, la fuite passe plus d'une fois sur deux. C'est la limite honnête du mécanisme — une fuite plus petite que le bruit d'estimation n'est pas distinguable du bruit, et aucun test à échantillon fini ne peut faire mieux.

### Le jeu D est le plus important

Aucun candidat n'a d'edge, et il n'y a **aucune fuite** : le gagnant est désigné par le seul bruit. C'est du surapprentissage pur, sans look-ahead — précisément ce que le garde-fou **n'est pas conçu pour attraper**.

Avec le seuil du projet, il certifie `agrees` dans **52.0%** des cas. Seuil neutralisé, ce chiffre monte à **53.0%**.

**Avec le seuil réellement utilisé par ce projet — 0.0 — le seuil ne protège de rien : le neutraliser complètement ne déplace le chiffre que de 1.0 point.** Sur une sélection sans le moindre edge, rien dans la chaîne ne s'y oppose : ni le garde-fou, qui n'est pas conçu pour ça et le dit, ni le seuil, qui est à zéro.

*Correction du 28/08/2026, et elle porte sur ce même paragraphe.* Une première version de ce banc employait un seuil de **0.3** en le présentant comme « celui du projet ». Vérification faite, le projet utilise **0.0** partout — `agent.py`, `backtest.py`, et les deux appels de `compare_strategies.py`. Avec le faux seuil, `NO EDGE` couvrait 27.4 % des cas et la conclusion publiée ici était que « c'est le seuil de Sharpe qui protège ». C'était faux, et faux parce que la mesure reposait sur une constante que personne n'avait vérifiée — exactement l'erreur que ce projet existe pour attraper, commise dans l'outil écrit pour l'auditer.

Ce que la correction change, en clair : le résultat est **plus sévère**, pas moins. Le garde-fou certifie une sélection sans valeur une fois sur deux, et aucun autre mécanisme ne rattrape ça. C'est un argument mesuré en faveur d'un seuil de Sharpe non nul — décision de méthode qui appartient à l'opérateur, pas une modification à faire en douce à huit jours du rendu.

## Courbe de détection (jeu C)

| taille de fuite δ | `LEAK DETECTED` | `agrees` | `NO EDGE` |
|---|---|---|---|
| 0.00 | 31.6% | 68.4% | 0.0% |
| 0.15 | 33.5% | 66.5% | 0.0% |
| 0.30 | 38.4% | 61.6% | 0.0% |
| 0.45 | 45.8% | 54.2% | 0.0% |
| 0.60 | 54.2% | 45.8% | 0.0% |
| 0.80 | 68.5% | 31.5% | 0.0% |
| 1.00 | 81.2% | 18.8% | 0.0% |
| 1.40 | 93.0% | 7.0% | 0.0% |
| 2.00 | 94.6% | 5.4% | 0.0% |

À δ=0 il n'y a **pas** de fuite : la ligne δ=0.00 est donc un second témoin du taux de fausse alerte, obtenu par un chemin différent du jeu A.

## Le taux de fausse alerte n'est pas un chiffre, c'est une courbe

Le 30.2% du jeu A dépend de l'écart que j'ai mis entre le meilleur candidat et son suivant. Un chiffre qui dépend d'un paramètre arbitraire est exactement ce que ce projet reproche aux backtests des autres — voici donc l'écart balayé, à bruit constant (σ=0.30).

| écart réel meilleur − suivant | fausse alerte | `agrees` |
|---|---|---|
| 0.00 | 45.0% | 55.0% |
| 0.10 | 44.5% | 55.5% |
| 0.20 | 41.1% | 58.9% |
| 0.30 | 35.6% | 64.4% |
| 0.40 | 31.8% | 68.2% |
| 0.60 | 18.1% | 81.9% |
| 0.80 | 7.8% | 92.2% |
| 1.20 | 0.7% | 99.3% |

**Ce n'est pas un bug, c'est le prix du test.** Quand deux candidats sont statistiquement indiscernables, refuser est la bonne réponse : on ne *peut* pas dire lequel est meilleur. La courbe dit simplement à partir de quelle séparation réelle le garde-fou cesse de payer ce prix.

## Une réserve sur le mot « LEAK »

Dans le jeu D il n'y a **aucune fuite** — et le garde-fou imprime pourtant `LEAK DETECTED` dans 47.4% des cas. Ce qu'il mesure réellement, c'est l'**instabilité du gagnant entre les deux fenêtres**. Une fuite en est la cause la plus intéressante, pas la seule : le bruit d'estimation produit la même signature.

C'est une limite de vocabulaire, pas de code, et elle est assumée ici plutôt que corrigée en silence.

## Le banc retourné contre le projet lui-même

Le README affirme, sous le titre *« Honest fact worth surfacing »*, que `momentum_strategy.py` passe le garde-fou sur **4 symboles sur 4** tandis que `vol_strategy.py` n'en passe que **3 sur 4**. L'intention est honnête — c'est un résultat qui dessert la stratégie retenue. Mais personne n'avait demandé son intervalle à cette comparaison.

- Test exact de Fisher sur la table observée (4/0 contre 3/1) : **p = 1.000**.
- Si les deux stratégies étaient **identiques**, un écart d'au moins un symbole apparaîtrait quand même :

| taux de succès réel par symbole | écart ≥ 1 symbole observé |
|---|---|
| 0.70 | 69.7% |
| 0.80 | 64.0% |
| 0.85 | 58.2% |
| 0.90 | 48.2% |
| 0.95 | 30.7% |

**« Momentum est plus propre sur le test de fuite » est donc un tirage à pile ou face présenté comme un constat.** Le fait mérite d'être publié ; la comparaison ne mérite pas qu'on agisse dessus. Lire un signal dans un écart qui tient dans le bruit est exactement l'erreur que ce projet existe pour attraper — et il l'avait commise dans son propre README. C'est corrigé là-bas, avec ces chiffres.

## Ce que couterait un seuil non nul

Le jeu D montre qu'avec le seuil livré (**0.0**) rien ne protège contre une sélection sans edge. Le dire sans chiffrer l'alternative laisserait la décision en l'air.

| seuil | jeu D — certifie du BRUIT | jeu A — refuse un VRAI edge |
|---|---|---|
| 0.00 ← livré | 52.0 % | 30.2 % |
| 0.10 | 49.4 % | 30.2 % |
| 0.20 | 43.3 % | 30.2 % |
| 0.30 | 34.6 % | 30.2 % |
| 0.40 | 24.1 % | 30.4 % |
| 0.60 | 8.2 % | 33.3 % |

**Jusqu'à 0.30 le coût ne bouge pas** — 30.2 % dans les deux cas — pendant que le bruit certifié tombe de 52.0 % à 34.6 %. Ce n'est pas un arbitrage à cet endroit : c'est un gain sans contrepartie mesurable. L'arbitrage commence vers 0.60, où 8 % de bruit se paient 3.1 points de vrais edges refusés.

### Décision prise le 28/08/2026 : **le seuil reste à 0.0**

Décision de Spap, prise le jour du kickoff après avoir vu ces chiffres, et à revoir **après le 04/09**. Les raisons, dans l'ordre où elles pèsent :

1. **Les backtests publiés emploient 0.0.** Changer le seuil sans régénérer `BACKTEST_RESULTS.md` et `STRATEGY_COMPARISON.md` laisserait les livrables décrire une règle que l'agent n'applique plus — précisément le défaut que ce projet existe pour attraper.
2. **La semaine live est le seul résultat hors échantillon du dossier.** Ajuster un paramètre la veille, c'est en faire un énième backtest ajusté.
3. Le gain est mesuré sur un **modèle synthétique**, pas sur la vraie distribution des Sharpe.

La mesure reste publiée telle quelle. *« Voici notre seuil, voici ce qu'il nous coûte, voici pourquoi nous ne l'avons pas touché avant la semaine live »* est un meilleur argument que l'optimisation silencieuse — et c'est la thèse de ce projet appliquée à lui-même.

*Mesuré sur le modèle synthétique de ce banc (σ=0.30, ρ=0.70), pas sur la vraie distribution des Sharpe. Et changer ce seuil invaliderait les backtests publiés, qui emploient 0.0 : c'est une décision de méthode, pas un réglage.*

## Ce que ce banc ne démontre pas

- La vérité-terrain est construite **au niveau des scores**, pas des prix. C'est le contrat réel de `check_selection_leakage`, et c'est le seul moyen de contrôler exactement la taille d'effet — mais cela ne démontre pas que le pipeline de prix produit ces situations-là.
- Le bruit est gaussien et homoscédastique. Les vrais Sharpe d'échantillon ne le sont pas.
- Cinq candidats, une seule fuite injectée à la fois. Pas de correction pour tests multiples.

**Formulation défendable de la promesse, compte tenu de ces mesures :** *Hindsight tests whether a model's parameter selection remains stable when information unavailable at decision time is removed.* Ni plus, ni moins.
