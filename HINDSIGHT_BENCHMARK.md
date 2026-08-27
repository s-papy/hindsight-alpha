# hindsight_guard — caractérisation sur vérité-terrain connue

*Généré par `hindsight_benchmark.py`. 4000 essais par condition, graine fixe (20260827) — reproductible à l'identique.*

Ce banc ne mesure pas si la stratégie gagne de l'argent. Il mesure **ce que le détecteur détecte**, avec quel taux de fausse alerte, à partir de quelle taille d'effet, et surtout **ce qu'il ne détecte pas**.

Paramètres : seuil de Sharpe **0.30**, bruit d'estimation σ=**0.30**, corrélation des deux fenêtres ρ=**0.70** (elles sont notées sur des données qui se recouvrent — les traiter comme indépendantes gonflerait artificiellement le taux de fausse alerte).

## Les quatre jeux

| jeu | vérité-terrain | `agrees` | `LEAK DETECTED` | `NO EDGE` | `CANNOT CONCLUDE` |
|---|---|---|---|---|---|
| **A** — edge réel, aucune fuite | *pas de fuite* | 69.8% | 30.2% | 0.0% | 0.0% |
| **B** — fuite évidente (δ=1.20) | *fuite* | 11.8% | 88.2% | 0.0% | 0.0% |
| **D** — aucun edge, aucune fuite | *surapprentissage seul* | 34.6% | 38.0% | 27.4% | 0.0% |
| **D-bis** — idem, seuil neutralisé | *surapprentissage seul* | 53.0% | 47.0% | 0.0% | 0.0% |

## Ce que ces chiffres disent

**Taux de fausse alerte : 30.2%** (jeu A). Sur une sélection réellement stable, le garde-fou se trompe dans 30.2% des cas — il refuse de valider une stratégie qui n'avait rien à se reprocher. Ce n'est pas gratuit : chaque fausse alerte est un trade non pris.

**Taux de détection sur fuite franche : 88.2%** (jeu B).

**Seuil de sensibilité : δ ≈ 0.60.** En dessous, la fuite passe plus d'une fois sur deux. C'est la limite honnête du mécanisme — une fuite plus petite que le bruit d'estimation n'est pas distinguable du bruit, et aucun test à échantillon fini ne peut faire mieux.

### Le jeu D est le plus important

Aucun candidat n'a d'edge, et il n'y a **aucune fuite** : le gagnant est désigné par le seul bruit. C'est du surapprentissage pur, sans look-ahead — précisément ce que le garde-fou **n'est pas conçu pour attraper**.

Avec le seuil du projet, il certifie `agrees` dans **34.6%** des cas. Seuil neutralisé, ce chiffre monte à **53.0%**.

La conclusion est nette, et elle limite la promesse du projet : **ce n'est pas `hindsight_guard` qui protège contre une sélection sans edge, c'est le seuil de Sharpe.** Les deux mécanismes sont distincts et il ne faut pas créditer le premier du travail du second.

## Courbe de détection (jeu C)

| taille de fuite δ | `LEAK DETECTED` | `agrees` | `NO EDGE` |
|---|---|---|---|
| 0.00 | 31.6% | 68.4% | 0.0% |
| 0.15 | 33.6% | 66.4% | 0.0% |
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
| 0.00 | 45.2% | 54.8% |
| 0.10 | 44.7% | 55.3% |
| 0.20 | 41.2% | 58.8% |
| 0.30 | 35.7% | 64.3% |
| 0.40 | 32.0% | 68.0% |
| 0.60 | 18.1% | 81.9% |
| 0.80 | 7.8% | 92.2% |
| 1.20 | 0.7% | 99.3% |

**Ce n'est pas un bug, c'est le prix du test.** Quand deux candidats sont statistiquement indiscernables, refuser est la bonne réponse : on ne *peut* pas dire lequel est meilleur. La courbe dit simplement à partir de quelle séparation réelle le garde-fou cesse de payer ce prix.

## Une réserve sur le mot « LEAK »

Dans le jeu D il n'y a **aucune fuite** — et le garde-fou imprime pourtant `LEAK DETECTED` dans 38.0% des cas. Ce qu'il mesure réellement, c'est l'**instabilité du gagnant entre les deux fenêtres**. Une fuite en est la cause la plus intéressante, pas la seule : le bruit d'estimation produit la même signature.

C'est une limite de vocabulaire, pas de code, et elle est assumée ici plutôt que corrigée en silence.

## Ce que ce banc ne démontre pas

- La vérité-terrain est construite **au niveau des scores**, pas des prix. C'est le contrat réel de `check_selection_leakage`, et c'est le seul moyen de contrôler exactement la taille d'effet — mais cela ne démontre pas que le pipeline de prix produit ces situations-là.
- Le bruit est gaussien et homoscédastique. Les vrais Sharpe d'échantillon ne le sont pas.
- Cinq candidats, une seule fuite injectée à la fois. Pas de correction pour tests multiples.

**Formulation défendable de la promesse, compte tenu de ces mesures :** *Hindsight tests whether a model's parameter selection remains stable when information unavailable at decision time is removed.* Ni plus, ni moins.
