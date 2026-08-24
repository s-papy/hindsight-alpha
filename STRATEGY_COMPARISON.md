# Strategy comparison — vol_strategy (HV-rank) vs momentum_strategy (TSMOM)

*Generated 2026-08-24T19:08:40.963000+00:00, real bars via alpaca_cli.get_daily_bars.*

**Read compare_strategies.py's module docstring before quoting any single number below** — the two families' payoffs are different units (options proxy vs real stock return) and are not directly summable or comparable as raw magnitudes. What IS comparable per symbol: hindsight_guard agreement (is either one's winner an actual leak), and the in-sample Sharpe of each vetted parameter (same statistic, same holdout window length, same computation) — that's the fairest apples-to-apples number.

| symbol | vol_strategy: window | agrees? | in-sample Sharpe | win rate | momentum: lookback | agrees? | in-sample Sharpe | win rate |
|---|---|---|---|---|---|---|---|---|
| SPY | 10d | yes | 1.598 | 45.1% | 60d | yes | 0.63 | 54.4% |
| GLD | 20d | yes | 1.956 | 57.1% | 60d | yes | 1.407 | 54.5% |
| XLK | 90d | **LEAK** | 0.789 | 36.8% | 20d | yes | 0.593 | 51.4% |
| XLV | 10d | yes | 1.442 | 50.0% | 40d | yes | 0.812 | 50.2% |

## Detail per symbol

### SPY (657 bars used)

- **vol_strategy** — vetted window 10d, hindsight_guard agrees (no leak), in-sample Sharpe 1.598, 102/393 days traded (45.1% win rate on those days), cumulative proxy payoff 0.1073.
- **momentum_strategy** — vetted lookback 60d, hindsight_guard agrees (no leak), in-sample Sharpe 0.63, 596 days traded (always in the market), 54.4% win rate, cumulative return 26.83%.

### GLD (657 bars used)

- **vol_strategy** — vetted window 20d, hindsight_guard agrees (no leak), in-sample Sharpe 1.956, 56/383 days traded (57.1% win rate on those days), cumulative proxy payoff 0.1467.
- **momentum_strategy** — vetted lookback 60d, hindsight_guard agrees (no leak), in-sample Sharpe 1.407, 596 days traded (always in the market), 54.5% win rate, cumulative return 65.52%.

### XLK (657 bars used)

- **vol_strategy** — vetted window 90d, hindsight_guard LEAK DETECTED, in-sample Sharpe 0.789, 76/313 days traded (36.8% win rate on those days), cumulative proxy payoff 0.416.
- **momentum_strategy** — vetted lookback 20d, hindsight_guard agrees (no leak), in-sample Sharpe 0.593, 636 days traded (always in the market), 51.4% win rate, cumulative return 48.88%.

### XLV (657 bars used)

- **vol_strategy** — vetted window 10d, hindsight_guard agrees (no leak), in-sample Sharpe 1.442, 52/393 days traded (50.0% win rate on those days), cumulative proxy payoff 0.1289.
- **momentum_strategy** — vetted lookback 40d, hindsight_guard agrees (no leak), in-sample Sharpe 0.812, 616 days traded (always in the market), 50.2% win rate, cumulative return 36.03%.

## Honest verdict — written 24/08 AFTER the first real run, not before

**Sur le seul chiffre comparable (Sharpe in-sample du paramètre vetté, même statistique, même holdout) : `vol_strategy` gagne sur les 4 symboles.**

| symbole | vol_strategy | momentum | écart |
|---|---|---|---|
| SPY | **1,598** | 0,630 | +0,97 |
| GLD | **1,956** | 1,407 | +0,55 |
| XLK | 0,789 🔴 *(fuite)* | 0,593 | — *(vol disqualifié)* |
| XLV | **1,442** | 0,812 | +0,63 |

🔴 **Mais `momentum` est plus PROPRE : `hindsight_guard` l'approuve 4 fois sur 4, contre 3 sur 4 pour `vol_strategy`** (XLK fuit). *Un score plus haut sur trois symboles, contre une discipline de sélection parfaite sur quatre — ce n'est pas la même chose, et ça ne se tranche pas au seul Sharpe.*

⚠️ **Ce qu'il ne faut SURTOUT pas faire avec ce tableau** : comparer les rendements cumulés. `momentum` est **en permanence dans le marché** (596 à 636 jours sur ~650), donc son « +65,52 % » sur GLD est essentiellement du buy-and-hold avec un filtre de tendance — sur la même période, GLD seul a fait **+126,96 %**. `vol_strategy` n'est en position que 10 à 28 % des jours, avec un payoff proxy en unités différentes. **Les deux colonnes de rendement ne sont pas commensurables**, et les additionner ou les classer serait une faute.

**Décision : aucune.** *Le brief interdit explicitement de basculer l'agent sur `momentum` sur la foi de ce tableau — c'est une décision de méthode qui appartient à Spap. Elle est simplement documentée ici, avec le chiffre qui la motiverait dans un sens (Sharpe) et celui qui la motiverait dans l'autre (propreté du garde-fou).*
