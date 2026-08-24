# Strategy comparison — vol_strategy (HV-rank) vs momentum_strategy (TSMOM)

*Generated 2026-08-24T21:07:59.847672+00:00, real bars via alpaca_cli.get_daily_bars.*

**Read compare_strategies.py's module docstring before quoting any single number below** — the two families' payoffs are different units (options proxy vs real stock return) and are not directly summable or comparable as raw magnitudes. What IS comparable per symbol: hindsight_guard agreement (is either one's winner an actual leak), and the in-sample Sharpe of each vetted parameter (same statistic, same holdout window length, same computation).

🔴 **But do not read that Sharpe column as a verdict on its own.** An earlier version of this file called it "the fairest apples-to-apples number"; measuring it showed that overclaims. The two Sharpes share a FORMULA, not a quantity: vol_strategy's payoff is built on `abs(next-day return)` — non-negative by construction, and ~25% less variable than the signed return — and it is flat on roughly three days out of four, which shrinks its standard deviation again. momentum's is a signed return, in the market almost every day. Measured on the 24/08 bars: momentum had the HIGHER mean daily figure on 3 of the 4 symbols, while vol_strategy had the higher Sharpe on 4 of 4 — the ranking inverts with the statistic you pick, because vol_strategy's advantage here is variance structure, not superior returns. The mean and standard-deviation columns below are printed so that is visible instead of buried.

| symbol | vol_strategy: window | agrees? | in-sample Sharpe | win rate | momentum: lookback | agrees? | in-sample Sharpe | win rate |
|---|---|---|---|---|---|---|---|---|
| SPY | 10d | yes | 1.598 | 45.1% | 60d | yes | 0.63 | 54.4% |
| GLD | 20d | yes | 1.956 | 57.1% | 60d | yes | 1.407 | 54.5% |
| XLK | 90d | **LEAK** | 0.789 | 36.8% | 20d | yes | 0.593 | 51.4% |
| XLV | 10d | yes | 1.442 | 50.0% | 40d | yes | 0.812 | 50.2% |

## Detail per symbol

### SPY (657 bars used)

- **vol_strategy** — vetted window 10d, hindsight_guard agrees (no leak), in-sample Sharpe 1.598 (mean/day +0.00027, sd/day 0.00276), 102/393 days traded (45.1% win rate on those days), cumulative proxy payoff 0.108.
- **momentum_strategy** — vetted lookback 60d, hindsight_guard agrees (no leak), in-sample Sharpe 0.63 (mean/day +0.00045, sd/day 0.0102), 596 days traded (always in the market), 54.4% win rate, cumulative return 26.76%.

### GLD (657 bars used)

- **vol_strategy** — vetted window 20d, hindsight_guard agrees (no leak), in-sample Sharpe 1.956 (mean/day +0.00038, sd/day 0.00319), 56/383 days traded (57.1% win rate on those days), cumulative proxy payoff 0.1467.
- **momentum_strategy** — vetted lookback 60d, hindsight_guard agrees (no leak), in-sample Sharpe 1.407 (mean/day +0.0011, sd/day 0.01441), 596 days traded (always in the market), 54.5% win rate, cumulative return 65.83%.

### XLK (657 bars used)

- **vol_strategy** — vetted window 90d, hindsight_guard LEAK DETECTED, in-sample Sharpe 0.789 (mean/day +0.00133, sd/day 0.02763), 76/313 days traded (36.8% win rate on those days), cumulative proxy payoff 0.416.
- **momentum_strategy** — vetted lookback 20d, hindsight_guard agrees (no leak), in-sample Sharpe 0.593 (mean/day +0.00076, sd/day 0.02573), 636 days traded (always in the market), 51.4% win rate, cumulative return 48.57%.

### XLV (657 bars used)

- **vol_strategy** — vetted window 10d, hindsight_guard agrees (no leak), in-sample Sharpe 1.442 (mean/day +0.00033, sd/day 0.00293), 52/393 days traded (50.0% win rate on those days), cumulative proxy payoff 0.1289.
- **momentum_strategy** — vetted lookback 40d, hindsight_guard agrees (no leak), in-sample Sharpe 0.812 (mean/day +0.00059, sd/day 0.00971), 616 days traded (always in the market), 50.2% win rate, cumulative return 36.07%.

## Honest verdict — écrit le 24/08 APRÈS la mesure, corrigé le même soir

**Le classement s'inverse selon la statistique choisie. C'est le fait le plus important de ce tableau.**

| | vol_strategy | momentum | |
|---|---|---|---|
| **Sharpe in-sample du paramètre vetté** | plus haut sur **4 symboles sur 4** | — | |
| **moyenne par jour calendaire** | — | plus haute sur **3 symboles sur 4** | 🔴 |
| **propreté `hindsight_guard`** | 3 / 4 *(XLK fuit)* | **4 / 4** | 🔴 |

🔴 **Correction d'une version antérieure de ce verdict.** J'avais écrit que `vol_strategy` gagne sur le Sharpe et présenté ce chiffre comme *« le seul comparable »*. **Mesuré, ça surestime.** Sur SPY : `momentum` a la moyenne quotidienne la plus haute (+0,00045 contre +0,00027) et perd malgré tout le Sharpe, parce que son écart-type est **3,7× plus grand** (0,0102 contre 0,00276).

**D'où vient cet écart-type minuscule ?** De deux effets qui n'ont rien à voir avec la qualité du signal : `vol_strategy` est **à plat ~3 jours sur 4**, et son payoff repose sur `abs(rendement)` — non négatif par construction, et **~25 % moins variable** que le rendement signé. **Son avantage au Sharpe est structurel, pas une supériorité de rendement.**

⚠️ **Et surtout, ne jamais classer les rendements cumulés** : `momentum` est en permanence dans le marché, donc son « +65,83 % » sur GLD est essentiellement du buy-and-hold filtré — GLD seul a fait **+126,96 %** sur la même période.

**Décision : aucune.** *Basculer la stratégie appartient à Spap. Ce document donne désormais les trois chiffres qui tirent dans des sens différents, plutôt qu'un seul qui tranche à sa place.*
