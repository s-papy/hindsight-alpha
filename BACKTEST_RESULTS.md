# Backtest results — HV-rank strategy vs real historical bars

*Generated 2026-08-24T21:13:27.919576+00:00. Proxy payoff, not real options P&L — see backtest.py's module docstring for exactly what is and isn't simulated.*

## SPY (657 bars used)

*Buy-and-hold over the same bars: **60.2%**. 🔴 This is NOT comparable to the payoff column below and must never be ranked against it: buy-and-hold is a compounded price return over every day of the period, while `cum. proxy payoff` is a SUM of daily `abs(return) - cost` payoffs on the minority of days the rule was in a position at all. Different quantities, different denominators. It is printed for context on what the underlying did, not as a benchmark to beat.*

| window (days) | trade days | freq | cum. proxy payoff | win rate on trades | avg payoff/trade | max drawdown (proxy units) |
|---|---|---|---|---|---|---|
| 10 | 102/393 | 26.0% | 0.108 | 45.1% | 0.00106 | -0.0241 |
| 20 | 106/383 | 27.7% | -0.0341 | 32.1% | -0.00032 | -0.0877 |
| 30 | 111/373 | 29.8% | -0.1054 | 23.4% | -0.00095 | -0.1273 |
| 60 | 102/343 | 29.7% | -0.0977 | 29.4% | -0.00096 | -0.1262 |
| 90 | 100/313 | 31.9% | -0.1406 | 26.0% | -0.00141 | -0.1586 |

🔴 **Concentration — share of each positive total earned on its best 5 trade days:** 10d: **82.6%**. *A share ABOVE 100% is not an error: it means those five days earned more than the entire net result, i.e. every other trade day combined lost money.* A long-optionality rule is *expected* to earn on a handful of large moves, so this is the payoff's signature rather than an anomaly — but it means a positive total built from ~100 trades does not distinguish an edge from luck, and that the omitted costs (spread, theta) would bite hardest on exactly what remains after those days are removed.

**hindsight_guard verdict for this symbol:** agrees (no leak) — full-window winner: 10 days, in-sample winner: 10 days.

## GLD (657 bars used)

*Buy-and-hold over the same bars: **127.57%**. 🔴 This is NOT comparable to the payoff column below and must never be ranked against it: buy-and-hold is a compounded price return over every day of the period, while `cum. proxy payoff` is a SUM of daily `abs(return) - cost` payoffs on the minority of days the rule was in a position at all. Different quantities, different denominators. It is printed for context on what the underlying did, not as a benchmark to beat.*

| window (days) | trade days | freq | cum. proxy payoff | win rate on trades | avg payoff/trade | max drawdown (proxy units) |
|---|---|---|---|---|---|---|
| 10 | 62/393 | 15.8% | 0.0533 | 46.8% | 0.00086 | -0.0301 |
| 20 | 56/383 | 14.6% | 0.1467 | 57.1% | 0.00262 | -0.0231 |
| 30 | 48/373 | 12.9% | 0.0579 | 47.9% | 0.00121 | -0.0413 |
| 60 | 34/343 | 9.9% | -0.0105 | 41.2% | -0.00031 | -0.0391 |
| 90 | 18/313 | 5.8% | 0.079 | 55.6% | 0.00439 | -0.0176 |

🔴 **Concentration — share of each positive total earned on its best 5 trade days:** 10d: **145.8%** · 20d: **68.5%** · 30d: **150.2%** · 90d: **96.2%**. *A share ABOVE 100% is not an error: it means those five days earned more than the entire net result, i.e. every other trade day combined lost money.* A long-optionality rule is *expected* to earn on a handful of large moves, so this is the payoff's signature rather than an anomaly — but it means a positive total built from ~100 trades does not distinguish an edge from luck, and that the omitted costs (spread, theta) would bite hardest on exactly what remains after those days are removed.

**hindsight_guard verdict for this symbol:** agrees (no leak) — full-window winner: 20 days, in-sample winner: 20 days.

## XLK (657 bars used)

*Buy-and-hold over the same bars: **-5.56%**. 🔴 This is NOT comparable to the payoff column below and must never be ranked against it: buy-and-hold is a compounded price return over every day of the period, while `cum. proxy payoff` is a SUM of daily `abs(return) - cost` payoffs on the minority of days the rule was in a position at all. Different quantities, different denominators. It is printed for context on what the underlying did, not as a benchmark to beat.*

| window (days) | trade days | freq | cum. proxy payoff | win rate on trades | avg payoff/trade | max drawdown (proxy units) |
|---|---|---|---|---|---|---|
| 10 | 109/393 | 27.7% | 0.0711 | 43.1% | 0.00065 | -0.0532 |
| 20 | 90/383 | 23.5% | -0.048 | 38.9% | -0.00053 | -0.1151 |
| 30 | 85/373 | 22.8% | -0.0815 | 36.5% | -0.00096 | -0.1448 |
| 60 | 84/343 | 24.5% | -0.1475 | 31.0% | -0.00176 | -0.1648 |
| 90 | 76/313 | 24.3% | 0.416 | 36.8% | 0.00547 | -0.1059 |

🔴 **Concentration — share of each positive total earned on its best 5 trade days:** 10d: **181.6%** · 90d: **136.7%**. *A share ABOVE 100% is not an error: it means those five days earned more than the entire net result, i.e. every other trade day combined lost money.* A long-optionality rule is *expected* to earn on a handful of large moves, so this is the payoff's signature rather than an anomaly — but it means a positive total built from ~100 trades does not distinguish an edge from luck, and that the omitted costs (spread, theta) would bite hardest on exactly what remains after those days are removed.

**hindsight_guard verdict for this symbol:** LEAK DETECTED — full-window winner: 90 days, in-sample winner: 10 days.

## XLV (657 bars used)

*Buy-and-hold over the same bars: **23.93%**. 🔴 This is NOT comparable to the payoff column below and must never be ranked against it: buy-and-hold is a compounded price return over every day of the period, while `cum. proxy payoff` is a SUM of daily `abs(return) - cost` payoffs on the minority of days the rule was in a position at all. Different quantities, different denominators. It is printed for context on what the underlying did, not as a benchmark to beat.*

| window (days) | trade days | freq | cum. proxy payoff | win rate on trades | avg payoff/trade | max drawdown (proxy units) |
|---|---|---|---|---|---|---|
| 10 | 52/393 | 13.2% | 0.1289 | 50.0% | 0.00248 | -0.0294 |
| 20 | 40/383 | 10.4% | 0.0238 | 37.5% | 0.0006 | -0.0248 |
| 30 | 36/373 | 9.7% | 0.0377 | 33.3% | 0.00105 | -0.0226 |
| 60 | 40/343 | 11.7% | -0.039 | 35.0% | -0.00097 | -0.0452 |
| 90 | 66/313 | 21.1% | -0.0868 | 31.8% | -0.00132 | -0.1074 |

🔴 **Concentration — share of each positive total earned on its best 5 trade days:** 10d: **78.2%** · 20d: **282.5%** · 30d: **199.6%**. *A share ABOVE 100% is not an error: it means those five days earned more than the entire net result, i.e. every other trade day combined lost money.* A long-optionality rule is *expected* to earn on a handful of large moves, so this is the payoff's signature rather than an anomaly — but it means a positive total built from ~100 trades does not distinguish an edge from luck, and that the omitted costs (spread, theta) would bite hardest on exactly what remains after those days are removed.

**hindsight_guard verdict for this symbol:** agrees (no leak) — full-window winner: 10 days, in-sample winner: 10 days.
