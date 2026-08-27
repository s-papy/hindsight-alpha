# Hindsight Alpha

[![garde-fou](https://github.com/s-papy/hindsight-alpha/actions/workflows/garde-fou.yml/badge.svg)](https://github.com/s-papy/hindsight-alpha/actions/workflows/garde-fou.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Paper trading only](https://img.shields.io/badge/trading-paper%20only-brightgreen.svg)](#status)

**An options-trading agent that refuses to trade when its own parameter
selection fails an out-of-sample check — re-run before every decision, not once
at design time.**

Entry for the **Alpaca AI Trading Agents Hackathon** (lablab.ai, deadline
04/09/2026). Team: Hindsight Alpha.

**Public dashboard: [s-papy.github.io/hindsight-alpha](https://s-papy.github.io/hindsight-alpha)** —
every run, every refusal, every real order. It is a *snapshot*, not a live feed: republished every
30 minutes on weekdays from 15:30 to 22:00 CEST, plus once at 22:05 after the US close. The page
says so itself when it goes stale.

| | |
|---|---|
| **The mechanism** | scores each parameter twice — full history vs. yesterday-only — and refuses the symbol when the two winners disagree |
| **Does it catch anything real?** | yes: XLK is refused live, every run, on real bars |
| **Risk** | paper trading only, enforced in code; per-trade, total-exposure, sector, drawdown and consecutive-loss caps |
| **Proof it runs** | real paper order filled and closed; 12 offline regression tests; CI green on every push |

### TL;DR

For each symbol, the agent sweeps 5 volatility-window candidates and scores
every one **twice** — once on the full price history, once on only what would
have been knowable *yesterday*. If the two winners disagree, it **refuses to
trade that symbol** rather than quietly trusting whichever version looks better.

On real historical bars, that check finds a genuine disagreement on **XLK** and
refuses it live, every run, while SPY, GLD and XLV pass clean.

The backtest edge on those three is real but thin and concentrated. **The
result worth judging is not the P&L** — it is that the refusal mechanism catches
an actual leak rather than a hypothetical one, and re-checks it before every
decision instead of once at design time.

Paper trading only. Zero real funds at risk.

### Contents

| | |
|---|---|
| [Backtest, at a glance](#backtest-at-a-glance) | the four symbols, and what the numbers do *not* prove |
| [The problem this solves](#the-problem-this-solves) | why a clean-looking backtest can be measuring nothing |
| [What the agent does](#what-the-agent-does) | the pipeline, the risk gates, the prior art |
| [Setup](#setup-run-once-in-a-terminal) | install, credentials, first run |
| [Files](#files) | what each module is for |
| [Hosted dashboard](#hosted-dashboard) | how the public page is built without exposing a key |
| [Status](#status) | what is proven, what is running, what is left |

## Backtest, at a glance

*Every window tested, and the caveats around "concentration above 100%" and
proxy-payoff units: `BACKTEST_RESULTS.md`.*

| Symbol | Vetted window | `hindsight_guard` | Trades (of ~657 bars) | Win rate | Gain from best 5 days |
|---|---|---|---|---|---|
| SPY | 10d | ✅ clean | 102 | 45.1% | 82.6% |
| GLD | 20d | ✅ clean | 56 | 57.1% | 68.5% |
| XLV | 10d | ✅ clean | 52 | 50.0% | 78.2% |
| XLK | 90d | 🛡️ **LEAK — refused live** | 76 (not traded) | 36.8% | 136.7% |

A concentration share above 100% (XLK's 136.7%) isn't an error — it means
that symbol's best 5 days earned more than its entire net result, i.e. every
other trade day combined lost money; the long-optionality payoff is expected
to concentrate on a handful of large moves. High concentration on the three
clean symbols too (68.5–82.6%) means a positive result from ~50-100 trades
doesn't yet distinguish real edge from luck.

## The problem this solves

Most simple trading-signal agents pick a "best" parameter (a lookback
window, a threshold, a leverage cap) by sweeping candidates and scoring each
one against a chunk of historical data, then trading on the winner. The
silent failure: if the scoring window secretly includes data that would not
yet exist at decision time, the "winning" parameter only wins in hindsight —
not live. Nothing in the code looks wrong. The published backtest number is
real. It's just not measuring what it claims to.

This is the exact failure `hindsight_guard` — a small library written
earlier, vendored into this repo as `hindsight_guard.py` — was built to
catch, after finding it by hand in a real trading-strategy audit: a leverage cap chosen by Sharpe ratio over a
*total* period that quietly included a holdout window. In-sample-only, every
candidate scored negative.

## What the agent does

Each run evaluates a small universe of liquid, optionable ETFs — default
`SPY,GLD,XLK,XLV` (broad market, commodities, tech, healthcare), configurable
via `--symbols` — rather than a single symbol.

**Why several symbols, and why that isn't a loosened gate.** Three independent
"no" gates stacked on one low-volatility symbol made zero trades across the
whole judged week a realistic outcome. That would be honest, but the judging
weighs P&L performance, and a silent agent has nothing to show. Testing several
similarly-liquid symbols applies the *same* gate more times; it does not relax
it.

**Several positions at once, one per underlying.** Every symbol clearing every
gate gets a real entry attempt, not just the first. `risk_gates.py` enforces the
diversification directly: never two open positions on the same underlying, a
hard cap on concurrent positions (`MAX_OPEN_POSITIONS`), a 1%-of-equity
per-trade cap, and a 3%-of-equity cap on total premium across all open positions
combined — so stacking positions shrinks the room left for further ones instead
of each getting a fresh 1%.

The universe was chosen to be genuinely uncorrelated across sectors, so holding
several positions means different macro exposure, not the same bet three times
under different tickers. See `agent.evaluate_symbol()` and
`risk_gates.check_gates()`.

For each symbol:
1. Fetches daily bars via Alpaca's Market Data API.
2. Sweeps 5 candidate historical-volatility (HV) windows (10, 20, 30, 60, 90
   days) for a rule: *buy optionality when realized volatility is cheap
   relative to its own trailing 1-year distribution, sit out when it isn't.*
   This is deliberately options-native — the decision to trade is a
   volatility-regime call, not just a directional bet dressed up as an
   option. See `vol_strategy.py` for the honest documentation of what "HV
   rank" is a proxy for (real option IV history isn't available from
   Alpaca's market data) and what the backtest payoff simplifies.
3. Runs `hindsight_guard.check_selection_leakage`: scores every candidate
   window twice — once on the full bar history, once restricted to
   everything except the most recent 20 bars (what would actually have been
   knowable the day before "today"). Compares the two winners.
4. **If they disagree, if nothing clears the Sharpe bar in-sample, or if any
   candidate could not be scored at all, the agent refuses to trade and prints
   why.** This is the point of the project —
   not a better signal, but an agent honest about when its own selection
   process doesn't hold up out of sample.
5. If vetted, checks today's volatility regime with the trusted window. If
   volatility isn't cheap today, it sits out (a separate, ordinary "no edge"
   refusal — not a leakage problem). If it is cheap, a short-term momentum
   tiebreaker picks a direction and the agent finds a near-the-money option
   contract (call or put, 7–21 days to expiry) via Alpaca's options API.
6. Before submitting anything, `risk_gates.py` checks, for every symbol that
   cleared the gates above (not just the first): is the market open (skips
   cleanly on weekends/holidays), is a position already open on THIS
   underlying (never stacks a second one on the same symbol), is the
   concurrent-position cap already reached, does 1 contract fit inside the
   smaller of the 1%-of-equity per-trade cap and whatever's left under the
   3%-of-equity total exposure cap across all open positions (sizes down or
   skips instead of trading blind), and has the account dropped more than 3%
   from its recorded starting equity this week (a sticky lock — once
   tripped, no more trades until state.json is reset). Only if every gate
   clears does it submit a **paper** market order — and it can do this for
   more than one symbol in the same run.

### Risk gates

Required by the hackathon's one-page write-up ("risk gates" is one of the
three things it must cover) and, more importantly, because an agent that
can buy again every day with no cap on position count or capital at risk
isn't a trading agent — it's a liability generator with a good idea buried
inside it. See `risk_gates.py`:

- **Entry side**: up to `MAX_OPEN_POSITIONS` (4) open positions at once, one
  per underlying — never two on the same symbol simultaneously. A 1% of
  equity per-trade cap (sized from the contract's live ask price, or skipped
  if even 1 contract doesn't fit) AND a 3% of equity cap on the TOTAL
  premium committed across every open position combined, so a 2nd or 3rd
  concurrent position shrinks the budget left for further ones instead of
  each getting its own fresh 1%. A 3% drawdown lock that persists in `state.json`
  across days so a bad stretch actually stops the agent instead of letting it
  keep re-entering. **Named "weekly" in the code, but measured from the first
  equity ever recorded for the account, not from the start of each week** —
  there is no week-boundary reset. That is deliberate and on the safe side: it
  never releases on its own, matching the consecutive-loss breaker's "stop and
  let a human look" rule. The trade-off, stated plainly: a drawdown from a
  *peak* does not trip it if equity is still above the original baseline — this compares total account equity
  (already reflecting every open position combined) to the recorded
  starting equity, so it was already measuring combined drawdown, not a
  single isolated position.
- **Exit side**: `manage_exits()` runs first, before any new-entry
  evaluation, and closes any open position at +50% (take-profit) or -50%
  (stop-loss) on unrealized P&L — added after noticing the first draft only
  ever bought and never managed a position afterward, which would have left
  every trade unrealized (paper) until the judging window ended. Since 24/08
  it can also run on its own via `monitor_exits.py`, schedulable every
  15-30 minutes independent of the once-a-day entry cycle — see that file's
  docstring for why and how to schedule it.

### Agent-level controls (not strategy tweaks)

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

### Where this sits in the existing literature

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

### Why HV rank instead of momentum

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

### Why the CLI, not the SDK

The hackathon's hard requirement: *"MCP or CLI — projects must utilize
either Alpaca's MCP server or its CLI tools."* An earlier draft called the
`alpaca-py` SDK directly, which doesn't satisfy that. Switched to Alpaca's
official CLI (`github.com/alpacahq/cli`) instead of the MCP server because
Alpaca's own docs say so explicitly: the CLI is built for "scripts, cron,
CI, focused agent actions" (one command per call, then exit); the MCP
server is built for "long-lived AI sessions, multi-tool orchestration" with
a human-driven AI host attached (Claude Desktop, Cursor). This agent runs
as a scheduled sweep-then-decide command — the CLI's exact use case, not
the MCP server's. See `alpaca_cli.py` for the subprocess wrapper.

## What the agent needs to run

A normal terminal with outbound network access to `paper-api.alpaca.markets`
and `data.alpaca.markets`, plus the `alpaca` CLI binary. The code is written
to be unit-testable offline against mocked data, but any live run — placing a
paper order, reading real bars — needs that network access.

## Setup (run once, in a terminal)

```bash
# 1. Install the Alpaca CLI (not a pip package)
brew install alpacahq/tap/cli          # macOS/Linux
# or: go install github.com/alpacahq/cli/cmd/alpaca@latest
alpaca doctor                          # verify install

# 2. Python deps (just python-dotenv)
cd hindsight-alpha
pip install -r requirements.txt

# 3. Credentials
cp .env.example .env
# edit .env: paste your Alpaca PAPER key id + secret + account ID (from the
# Alpaca dashboard, Home page -> API Keys widget). Never the live-account keys.

# 4. Run
python3 -m unittest discover   # 206 offline tests, no credentials needed
python test_connection.py      # confirms CLI install + credentials + network
python agent.py --dry-run      # runs the full leakage check, no order placed
python agent.py                # if vetted, places a real (paper) options order
```

## Files

- `hindsight_guard.py` — the leakage-detection library, vendored here so the
  agent has no dependency on a sibling repository.
- `vol_strategy.py` — HV-rank strategy, candidate windows, the full-window
  vs in-sample scoring functions.
- `alpaca_cli.py` — subprocess wrapper around Alpaca's official CLI: bar
  fetching, option contract lookup, paper order submission. This is what
  satisfies the hackathon's "MCP or CLI" requirement.
- `agent.py` — main pipeline (market check → fetch → sweep → leakage check
  → risk gates → trade or refuse).
- `risk_gates.py` — concurrent-position cap (one per underlying), per-trade
  risk cap, total-exposure cap across all open positions, sector
  concentration cap, weekly drawdown lock, consecutive-loss circuit
  breaker, manual pause switch, duplicate-order guard. State persists in
  `state.json` (gitignored, created on first run).
- `monitor_exits.py` — standalone exit-only monitor, schedulable
  independently of `agent.py`'s once-a-day cycle. See its module docstring
  for the "why".
- `launchagents/` — the four macOS scheduling definitions, versioned rather
  than living only on one machine: `launchagents/com.hindsightalpha.monitor-exits.plist`
  (every 15 minutes through the session, including the close),
  `launchagents/com.hindsightalpha.market-hours-awake.plist` (a `caffeinate` job that keeps
  the machine awake through market hours),
  `launchagents/com.hindsightalpha.publish-dashboard.plist` (see "Hosted dashboard" for why
  that one pushes automatically), and
  `launchagents/com.hindsightalpha.agent-daily.plist` (the entry-decision cycle,
  once per trading day).

  **This paragraph used to end with "`agent.py` itself is deliberately NOT
  scheduled — the entry decision is launched by hand, so a human sees it
  happen." That decision was reversed on 27/08, the evening before kickoff,
  and the reason is worth stating plainly: the P&L being judged runs for a
  week, and a human who is at work does not launch anything.** Keeping a human
  in the loop was the better principle right up until it meant the agent would
  place no trades at all — at which point it protects nobody and hides
  nothing. The honest trade is named rather than quietly dropped.

  What replaces the human as the stop: the `HALT` file. Creating a file named
  `HALT` at the repo root makes `check_gates()` refuse every new entry, while
  `monitor-exits` keeps managing positions already open. No code edit, no
  credential touched. The entry decision is now automatic; stopping it is
  still one file away.

  The schedule is 21:37 local (15:37 ET), twenty-three minutes before the US
  close. The odd minute is deliberate: `monitor-exits` fires at :00, :15,
  :30, :45, :52 and :58, and `agent.py` calls `manage_exits()` too — sharing
  a minute means both processes contend for `state.json`, whose lock waits
  only 10 seconds while a single CLI call can take 30. :37 is the middle of
  the largest free gap.
  That hour is not arbitrary: this strategy's signal is a volatility rank
  computed on DAILY CLOSES, and `get_daily_bars()` does not exclude today —
  mid-session, the most recent bar is today's PARTIAL one. The later the run,
  the closer that bar is to the real close. See the plist's own comment for
  the trade-off this accepts in exchange.
- `decision_log.py` — appends one JSON record per run to `decision_log.jsonl`
  (committed, not gitignored — it's evidence of what the agent decided and
  why, every day of the hackathon, not a secret).
- `publish_dashboard.py` — snapshots the live account, positions, and recent
  decisions into `docs/data.json` for the hosted dashboard.
- `docs/index.html` — the dashboard itself: a single static HTML page, no
  build step, no framework, fetches `./data.json` and renders it. Meant to
  be served by GitHub Pages from this repo's `docs/` folder — see "Hosted
  dashboard" below.
- `test_risk_gates.py` — regression tests for the risk gates and the exit
  chain: threshold units, boundary, exposure caps, the consecutive-loss
  breaker, per-position isolation when one close fails, unreadable P&L,
  contract selection, account switching.
- `test_agent.py` — the orchestration: what happens when an order submission
  times out (the order may have landed), what a startup refusal records, and
  what the scheduled LaunchAgents are allowed to do unattended.
- `test_integration.py` — both entry points end to end, with only the
  `alpaca_cli` boundary stubbed. For `agent.py`: strategy, hindsight guard,
  regime check, risk gates, sizing, order submission and logging all run for
  real. For `monitor_exits.py`: the close chain, the every-run status marker,
  and the heartbeat that keeps a persistent failure from flooding the published
  log. Deterministic synthetic price series, no network.
- `test_dashboard.py` — the published page's own JavaScript, extracted from
  `docs/index.html` and executed: verdict badges, the per-symbol line for every
  record shape the committed log still contains, the monitor health banner, the
  hindsight-leak counter. Skips cleanly when `node` is unavailable.

  All three are standard library only and fully mocked — no network, no
  credentials, no order. Run them with `python3 -m unittest discover -v`; CI
  runs the same command on every push.
- `test_connection.py` — run first; confirms CLI install + `.env` + network
  access all work.
- `config.py` — loads `.env`, hard-refuses to run against anything that
  looks like a live-trading configuration.
- `backtest.py` — real backtest of `vol_strategy.py` against real historical
  bars (not a proxy re-implementation — reuses the project's own scoring
  code). Writes `BACKTEST_RESULTS.md`. Run from a real terminal (needs
  network access to Alpaca's data API).
- `momentum_strategy.py` — a second strategy family (time-series momentum,
  TSMOM), written earlier as a second demonstration of the same
  hindsight_guard leak-check pattern. Not wired into `agent.py` (the live
  agent only trades HV-rank, the options-native strategy), but not dead
  code either — `compare_strategies.py` runs it against the same real bars
  as `vol_strategy.py` for an honest head-to-head — so the strategy kept is
  not simply the one that tells the best story.
- `compare_strategies.py` — real, side-by-side comparison of
  `vol_strategy.py` vs `momentum_strategy.py` on the same real bars.
  Writes `STRATEGY_COMPARISON.md`. See its module docstring for why the two
  families' raw payoffs aren't directly comparable numbers, and what is.
## Hosted dashboard

Required by the submission ("Demo application platform", "Application
URL"). Hosting choice: **GitHub Pages serving `docs/`**, not a separate
server — a pattern already proven on an earlier project. The reasoning: the public page never needs to see
an API key. `publish_dashboard.py` runs locally (wherever `agent.py` runs,
with real credentials in `.env`), writes a plain JSON snapshot, and that
snapshot — not a live connection — is what gets committed and served.
Nothing publicly reachable ever touches Alpaca directly.

Setup (once, in a terminal — already done):

```bash
python publish_dashboard.py         # writes docs/data.json
git add docs/ decision_log.py decision_log.jsonl publish_dashboard.py
git commit -m "add hosted dashboard"
git push
# then on GitHub: Settings -> Pages -> Deploy from branch -> main -> /docs
```

`launchagents/com.hindsightalpha.publish-dashboard.plist` runs
`publish_dashboard.py --git-push` every 30 minutes through the session, plus
once just after the close.

**This is a deliberate change to a rule this project used to hold.** Publishing
to the public repo was kept explicit each time, on the grounds that pushing is
a decision rather than a step. But the page is the submission's Application
URL, and the README calls it live — a rule that leaves it stale most of the
time was protecting the wrong thing. The push is now automatic, and the rule is
amended here rather than quietly ignored.

What makes that safe to automate is narrow and worth stating: `git_publish()`
scopes both its diff check and its commit to `docs/data.json` and
`decision_log.jsonl` explicitly. An unrelated file staged in the working tree
at that moment cannot be scooped into a commit whose message claims to be only
a dashboard snapshot.

**Verified in a real browser**, not just parsed offline: a local server and a
Chrome session confirmed all three sections render, zero console errors, and
the figures match `docs/data.json` exactly. Later edits to `docs/index.html`
were re-checked offline the same way — HTML tag balance, `node --check` on the
extracted JS, and a mocked-record test proving each rendering function's actual
output.

## License

MIT (`LICENSE`), as the competition requires: *"Submissions must be original
and MIT-compliant."* That means anyone — including a commercial entity — may
copy, modify and redistribute this code, the only obligation being to keep the
copyright notice. There is no way to enter this hackathon and keep the code
private; the two are mutually exclusive by the rules.

No credential ever reaches this repository. `.env` is gitignored and has never
been committed — the guard rail re-checks that against the full git history on
every run.

Paper trading is enforced in two independent layers, and the distinction
matters: `cli_env()` **removes** `ALPACA_LIVE_TRADE` from the environment
handed to the CLI, so the CLI cannot see it whatever its spelling; and
`require_credentials()` refuses to start on any value that isn't an explicitly
recognised falsy one. Unset is the normal, silent case.

## Status

Paper trading only, zero real funds at risk — enforced in `config.py`, which
refuses to start against anything resembling a live-trading configuration.

**Proven end-to-end against the real API**, not only against mocks:

- The CLI path works: a real paper option order was submitted and later closed
  by a real take-profit / stop-loss check.
- The multi-position controls fired for real — order
  `2e7ba582-3784-4c80-8abb-d1e4eb0a79eb`, 2 puts `SPY260831P00764000` at
  \$4.69. `HALT` blocked new entries without blocking an exit already in
  progress, and the duplicate-order guard triggered.
- `hindsight_guard` refused XLK live, on real bars — the mechanism catches a
  genuine leak, not a hypothetical one.
- The hosted dashboard was confirmed in a browser showing that real data.

**Running now**: `monitor_exits.py` on a `launchd` schedule. It once failed 11
times in a row — not a permissions or config fault, but because the machine was
asleep and `launchd` only fired it during brief maintenance wake-ups, too short
for Wi-Fi to reconnect before the network call timed out. Each failure timestamp
matched the system sleep log to the second. It recovered on its own.

That incident matters beyond itself: Alpaca does **not** support bracket/OCO
orders on options, confirmed against the real API. This client-side polling loop
is therefore the *only* mechanism protecting an open position, so during the
judged week the machine must stay powered and awake through US market hours. The
dashboard now shows a health banner — age of last check, consecutive-failure
count — so a gap like that is visible on the public page instead of only in a
local log.

**The schedule now covers the closing bell.** The exit monitor ran every 15
minutes from 15:00 to 21:45 local — but the US session closes at 22:00 local.
The last 15 minutes of every session, the highest-volume window of the day,
had no check. A position crossing its stop there would have stayed open until
the next morning's first check, roughly 17 hours later, through the entire
overnight gap. Two slots added at 21:52 and 21:58; the remaining blind spot is
2 minutes. Both scheduling definitions now live in `launchagents/` — before,
the only mechanism protecting an open position existed nowhere but one
machine.

**Keeping the machine awake is now a configuration, not a habit.** That
incident happened because staying awake depended on someone being at the
keyboard. `launchagents/com.hindsightalpha.market-hours-awake.plist` runs
`caffeinate` from 15:20 to 22:05 local time on weekdays, covering 13:30–20:00
UTC with ten minutes on either side. Verified: the agent starts, the assertion
appears in `pmset -g assertions`, system sleep is blocked.

It can only *keep* a machine awake — it cannot wake one already asleep. That
half needs one administrator command, run once:

```bash
sudo pmset repeat wakeorpoweron MTWRF 15:15:00
```

Together they close the gap: the scheduled event wakes the machine at 15:15,
the agent holds it awake through the close.

**Remaining gap, stated plainly**: the dedicated hackathon account
(`.env.hackathon`) has never been connected. Everything above ran on a
development paper account, deliberately, under the hackathon's own rule allowing
any paper account before kickoff. The rules require the dedicated account to
start at exactly \$100,000, and resetting a paper account to a specific balance
invalidates its API key — so connecting it is the first action on kickoff
morning, before anything else touches it.
