# Design notes — Hindsight Alpha

Le README répond à « qu'est-ce que c'est et est-ce que ça marche ». Ce
fichier répond à « pourquoi ces choix-là », pour qui veut creuser. Rien n'y
a été réécrit : ces sections vivaient dans le README et en sont descendues
le 30/08/2026, parce qu'un juge dispose de cinq à dix minutes et que le
README en demandait presque trente.

Le reste de la matière est dans ses propres documents :
[HINDSIGHT_HOLDOUT.md](HINDSIGHT_HOLDOUT.md),
[HINDSIGHT_BENCHMARK.md](HINDSIGHT_BENCHMARK.md),
[STRATEGY_COMPARISON.md](STRATEGY_COMPARISON.md),
[BACKTEST_RESULTS.md](BACKTEST_RESULTS.md),
[LIVE_WEEK.md](LIVE_WEEK.md) et [PROVENANCE.md](PROVENANCE.md).

## Agent-level controls (not strategy tweaks)

The strategy is not the deliverable — the agent is. These controls come from
an Alpaca-published reference architecture and a trading-agent architecture
guide, and live in `risk_gates.py` unless noted:

- **Sector concentration cap** (`MAX_SECTOR_EXPOSURE_PCT`, 1.5% of equity):
  caps committed premium per sector (`SECTOR_MAP`), not just per underlying.
  A no-op today (one symbol per sector, already covered by the duplicate-
  underlying block) but stops being one the moment the universe grows past
  one symbol per sector — coded now, while cheap to test, so diversification
  stays an enforced control rather than a policy that quietly stops holding.
- **Data-quality gate** (`alpaca_cli.get_daily_bars`): refuses to build a
  signal off bars that are stale (most recent bar older than 5 days — a
  frozen feed) or show an implausible single-day price jump (>50%, well
  above any real historical move for these ETFs) instead of trusting every
  fetch blindly. Raises `DataQualityError`, caught the same way any other
  per-symbol failure already is (see `agent.evaluate_symbol`).
- **Manual pause switch**: create a file named `HALT` next to the code and
  the agent stops opening new positions (exits still run) until it's
  removed — no code or credential changes needed to pause mid-week.
  Gitignored; a local operational control, not something to publish.
- **Duplicate-order guard**: a local record in `state.json` (independent of
  the live API) remembers which underlyings already got an order submitted
  today, so a crash-and-rerun of `agent.py` can't resubmit the same trade
  twice while waiting for the API to catch up.
- **Consecutive-loss circuit breaker** (`MAX_CONSECUTIVE_LOSSES`, 3): a
  losing streak from the agent's own stop-losses pauses new entries even
  before the weekly %-drawdown lock would trip — a fast losing streak is a
  real signal on its own, not just a fraction of a bigger number. Sticky
  like the weekly lock, cleared the same way, deliberately not
  self-resetting (a blocked agent can't produce the win that would clear
  it, which is the point — stop and let a human look, don't quietly retry).

## Where this sits in the existing literature

The central mechanism has prior art, and it is worth citing rather than
presenting `hindsight_guard` as sprung from nowhere.

The full-window-vs-in-sample disagreement test is a small, live-decision
version of a real family of techniques in quantitative finance aimed at the
same failure — a "winning" parameter that only wins because the selection
criterion secretly saw data it shouldn't have: **Probability of Backtest
Overfitting** and **combinatorially symmetric cross-validation** (Bailey,
Borwein, López de Prado & Zhu, 2015 — compare an in-sample winner against
its out-of-sample rank across symmetric partitions), and **walk-forward
optimization** (Pardo — re-validate that an optimal parameter stays optimal
as the window rolls forward), with the *spirit* of the **Deflated Sharpe
Ratio**'s "don't trust a Sharpe you haven't corrected for how many things
you tried" (Bailey & López de Prado, 2014).

**Said plainly, both what's borrowed and what's not**: `hindsight_guard`
borrows the core idea (an in-sample/out-of-sample winner disagreement is
evidence of overfitting) but skips the formal statistical machinery those
methods use — no multiple-testing correction across the 5 candidate windows,
no combinatorial partitions, no bootstrap. What it does differently from all
of the above: those methods validate a strategy **once, at design time**,
then deploy it. This agent re-runs the same disagreement test **before every
single live decision**, with a live refusal if it fails that day — a
parameter that passed yesterday can still be refused today. That's the
actual differentiator to lead with if a judge who knows this literature asks
"isn't this just walk-forward validation" — it's the same question, asked
every trade, not once.

## Why HV rank instead of momentum

The first version of this agent used a plain time-series-momentum signal
(same shape as the original `hindsight_guard` audit case) traded via
options. That's a directional bet that happens to be expressed with options
— it doesn't exploit anything specific to options. Switched to a
volatility-regime rule instead: it decides *whether options are worth
buying at all* before deciding direction, which is a more honest use of
the "options trading agent" brief. Trade-off written down for the judges:
it's realized-vol rank, not implied-vol rank, because Alpaca doesn't expose
historical option IV to sweep over — documented explicitly in
`vol_strategy.py` rather than glossed over.

**Honest fact worth surfacing here rather than only in `STRATEGY_COMPARISON.md`**:
on the same real bars, `momentum_strategy.py` (the strategy NOT actually
traded live) passes `hindsight_guard` clean on **4 of 4** symbols, while the
live strategy (`vol_strategy.py`) only passes on **3 of 4** — XLK leaks under
HV-rank. The strategy kept for real trading is the one that fits the
"options-native" brief better, not the one with the cleanest leak-check
record.

**And the difference is not statistically distinguishable.** Added 27/08 after
`hindsight_benchmark.py` made it measurable: on the observed table (momentum
4 pass / 0 fail, HV-rank 3 / 1), Fisher's exact test gives **p = 1.000**. If
the two strategies were *identical*, a one-symbol gap would still show up 48%
to 70% of the time at n=4, depending on the per-symbol pass rate. So "momentum
is cleaner on the leak check" is a coin flip reported as a finding — the fact
is worth disclosing, the comparison is not worth acting on. This project exists
to catch exactly that error, and it had committed it in its own README;
`compare_strategies.py` and `STRATEGY_COMPARISON.md` exist
specifically so that trade-off is measured and shown, not silently made and
hidden. No threshold was adjusted after seeing this.

## Why the CLI, not the SDK

The hackathon's hard requirement: *"MCP or CLI — projects must utilize
either Alpaca's MCP server or its CLI tools."* An earlier draft called the
`alpaca-py` SDK directly, which doesn't satisfy that. Switched to Alpaca's
official CLI (`github.com/alpacahq/cli`) instead of the MCP server because
Alpaca's own docs say so explicitly: the CLI fits "shell scripts, cron
jobs, CI pipelines, copy and paste runbooks, and focused agent actions"
(one command per call, then exit); the MCP server "aligns with long-lived
agent sessions where the host benefits from tool schemas, shared context,
and multi-tool orchestration." This agent runs
as a scheduled sweep-then-decide command — the CLI's exact use case, not
the MCP server's. See `alpaca_cli.py` for the subprocess wrapper.

