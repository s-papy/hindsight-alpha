# `IN_SAMPLE_HOLDOUT_DAYS = 20` — ce nombre a-t-il jamais été justifié ?

*Généré par `hindsight_holdout.py`. 500 essais par condition et par taille de holdout, graine fixe (20260827), séries de 500 barres — reproductible à l'identique.*

Le garde-fou compare un Sharpe calculé sur ~700 barres à un Sharpe calculé sur les mêmes barres **moins les 20 dernières**. Les deux séries se recouvrent donc à **97 %**. Une fuite confinée dans la queue doit déplacer un Sharpe de 700 jours assez fort pour faire changer le gagnant — et personne n'avait mesuré si 20 était un bon choix.

**Protocole.** L'anomalie est de taille **fixe** (les 20 derniers jours) et c'est le **holdout qui varie**. C'est la question intéressante : un holdout plus court que la fuite la laisse contaminer *aussi* le score in-sample — les deux scores voient la même chose, ils sont d'accord, et le test est aveugle par construction.

| holdout | fausse alerte (queue saine) | détection (queue anormale) | écart utile |
|---|---|---|---|
| 5 j | 8.4% | 9.4% | +1.0 pts |
| 10 j | 9.8% | 13.2% | +3.4 pts |
| 20 j ←  **livré** | 22.6% | 32.2% | +9.6 pts |
| 40 j | 32.2% | 36.6% | +4.4 pts |
| 80 j | 36.6% | 40.8% | +4.2 pts |

La colonne qui compte est la dernière : détection **moins** fausse alerte. Un holdout qui détecte 80 % du temps mais crie aussi 70 % du temps sur des données saines ne vaut rien — il ne distingue pas.

## Verdict

Meilleur écart utile sur cette grille : **holdout = 20 j** (+9.6 pts). Le projet livre **20 j** (+9.6 pts).

Plancher de significativité à 500 essais : une différence de pourcentages n'est lisible qu'au-delà de **~3.2 points**.

**Le choix livré est le meilleur de la grille, et son avance (5.2 pts) dépasse le plancher.** Ce nombre n'avait jamais été mesuré ; il l'est maintenant.

**Ce qui est robuste, en revanche, et ne dépend pas de ce départage :** la détection plafonne (32% à 20 j, 41% à 80 j) tandis que la fausse alerte, elle, continue de monter (23% → 37%). Au-delà de 20 jours on paie donc plus qu'on ne gagne — c'est la forme de la courbe qui le dit, pas son point maximum.

## Ce que cette mesure ne dit pas

- Une seule forme d'anomalie (un changement de régime de volatilité, facteur ×2.6). Une fuite peut prendre d'autres formes.
- Séries synthétiques à volatilité sinusoïdale. Ce n'est pas un marché.
- 500 essais par cellule : les écarts de moins de ~4 points ne sont pas significatifs.
- La règle de gagnant utilisée ici reproduit celle du garde-fou mais court-circuite ses autres verdicts (`NO EDGE`, `CANNOT CONCLUDE`) : on mesure le **désaccord de gagnants**, qui est le mécanisme sous-jacent, pas l'étiquette finale.
