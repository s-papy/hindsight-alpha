# Hindsight Alpha

Entry for the **Alpaca AI Trading Agents Hackathon** (lablab.ai, deadline
04/09/2026). Team: Hindsight Alpha.

An options-trading agent that refuses to trust its own parameter selection
until it's checked for hindsight leakage.

## The problem this solves

Most simple trading-signal agents pick a "best" parameter (a lookback
window, a threshold, a leverage cap) by sweeping candidates and scoring each
one against a chunk of historical data, then trading on the winner. The
silent failure: if the scoring window secretly includes data that would not
yet exist at decision time, the "winning" parameter only wins in hindsight —
not live. Nothing in the code looks wrong. The published backtest number is
real. It's just not measuring what it claims to.

This is the exact failure `hindsight_guard` (a small library built earlier,
see `../hindsight-guard/`) was written to catch, after finding it by hand in
a real trading-strategy audit: a leverage cap chosen by Sharpe ratio over a
*total* period that quietly included a holdout window. In-sample-only, every
candidate scored negative.

## What the agent does

Evaluates a small universe of liquid, optionable ETFs each run (default
`SPY,GLD,XLK,XLV` — broad market, commodities, tech, healthcare/pharma;
configurable via `--symbols`), not just one. With three independent "no"
gates stacked (hindsight check, volatility regime, risk gates) on a single
low-volatility symbol, a real risk was zero trades across the whole
hackathon week — honest, but the judging explicitly weighs "P&L
Performance," and a silent agent has nothing to show there or in the demo.
Testing several similarly-liquid symbols is the same honest gate applied
more times, not a loosened one. Since 24/08 the agent can also hold several
positions at once, one per underlying: *every* symbol that clears every gate
gets a real entry attempt, not just the first. `risk_gates.py` enforces the
diversification directly — never two open positions on the same underlying,
a hard cap on concurrent positions (`MAX_OPEN_POSITIONS`), a 1%-of-equity
per-trade cap, and a 3%-of-equity cap on TOTAL premium committed across all
open positions combined, so stacking positions shrinks the room left for
further ones rather than each getting its own fresh 1%. The universe itself
was chosen to be genuinely uncorrelated across sectors (not three
similarly-behaving broad-market ETFs) so that holding multiple positions at
once means different macro exposure, not the same bet three times under
different tickers. See `agent.evaluate_symbol()` and `risk_gates.check_gates()`.

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
4. **If they disagree, or nothing clears the Sharpe bar in-sample, the agent
   refuses to trade and prints why.** This is the point of the project —
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
  each getting its own fresh 1%. A 3% weekly drawdown lock that persists in
  `state.json` across days so a bad stretch actually stops the agent instead
  of letting it keep re-entering — this compares total account equity
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

Added 24/08, second pass, after asking directly "we improved the strategy,
but the agent is the real deliverable — what improves the agent?" and
researching both an Alpaca-published reference architecture and a separate
trading-agent architecture guide for concrete answers, not generic ones.
Four more controls, all in `risk_gates.py` unless noted, all with mocked
regression tests:

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

## Why this can't run inside Cowork's sandbox

Cowork's bash sandbox only allows outbound calls to an allowlisted set of
domains; `paper-api.alpaca.markets` and `data.alpaca.markets` are not on it,
and the `alpaca` CLI binary can't be installed/run there either. This code
was written and unit-testable there (with mocked/synthetic data), but live
testing requires a real terminal with normal internet access — hence this
being handed off to run on your Mac directly.

## Setup (run in a real terminal, not Cowork)

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
python test_connection.py      # confirms CLI install + credentials + network
python agent.py --dry-run      # runs the full leakage check, no order placed
python agent.py                # if vetted, places a real (paper) options order
```

## Files

- `hindsight_guard.py` — vendored copy of the leakage-detection library
  (canonical source: `../hindsight-guard/`).
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
  for the "why" and cron/launchd setup.
- `decision_log.py` — appends one JSON record per run to `decision_log.jsonl`
  (committed, not gitignored — it's evidence of what the agent decided and
  why, every day of the hackathon, not a secret).
- `publish_dashboard.py` — snapshots the live account, positions, and recent
  decisions into `docs/data.json` for the hosted dashboard.
- `docs/index.html` — the dashboard itself: a single static HTML page, no
  build step, no framework, fetches `./data.json` and renders it. Meant to
  be served by GitHub Pages from this repo's `docs/` folder — see "Hosted
  dashboard" below.
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
  as `vol_strategy.py` for an honest head-to-head, per Spap's direction not
  to keep the strategy that "tells the best story" without checking it's
  also the one the data actually supports.
- `compare_strategies.py` — real, side-by-side comparison of
  `vol_strategy.py` vs `momentum_strategy.py` on the same real bars.
  Writes `STRATEGY_COMPARISON.md`. See its module docstring for why the two
  families' raw payoffs aren't directly comparable numbers, and what is.
- `alpaca_client.py` — dead code from an earlier draft (alpaca-py SDK
  version, superseded by `alpaca_cli.py` for the hackathon's "MCP or CLI"
  requirement). Left in place because Cowork's sandbox can't delete files
  in this shared folder; nothing imports it. Safe to delete by hand.

*(Found 24/08, "cherche encore": this file list used to be split into two
disconnected halves by the "Hosted dashboard" section sitting in between —
the second half dangled with no heading, right after unrelated prose about
browser verification. Merged back into one list here.)*

## Hosted dashboard

Required by the submission ("Demo application platform", "Application
URL"). Hosting choice: **GitHub Pages serving `docs/`**, not a separate
server — same pattern already used for another of Spap's projects
(SNIPER's D31 dashboard). The reasoning: the public page never needs to see
an API key. `publish_dashboard.py` runs locally (wherever `agent.py` runs,
with real credentials in `.env`), writes a plain JSON snapshot, and that
snapshot — not a live connection — is what gets committed and served.
Nothing publicly reachable ever touches Alpaca directly.

Setup (once, in a real terminal — already done; see `BRIEF_DEBLOQUER_MONITOR_ET_KICKOFF.md`
for the current terminal handoff):

```bash
python publish_dashboard.py         # writes docs/data.json
git add docs/ decision_log.py decision_log.jsonl publish_dashboard.py
git commit -m "add hosted dashboard"
git push
# then on GitHub: Settings -> Pages -> Deploy from branch -> main -> /docs
```

After that, running `python publish_dashboard.py --git-push` at the end of
each day's `agent.py` run keeps the public page current. `--git-push` is
opt-in on purpose — writing the snapshot is safe to automate, publishing to
the public repo is a decision this project's own rules say should stay
explicit each time, not a silent default.

**Verified for real in a real browser** (not just parsed offline): a local
server + Chrome session confirmed all three sections render, zero console
errors, and the figures match `docs/data.json` exactly (see PLAN_SPRINT.md,
"session terminal n°2"). Every later change to `docs/index.html` (the
multi-symbol `renderTrade()` rewrite, the `exit_actions` rendering fix, the
`outcomeBadge()` signature change) was re-checked offline the same way the
first version was before that live check — HTML tag balance, `node --check`
on the extracted JS, and a mocked-record test proving each rendering
function's actual output — but **not re-opened in a live browser after
those later edits**. Worth one more quick look in an actual browser before
recording the demo video, to catch anything only a real render would show.

## License and privacy

This repo is public and MIT-licensed (`LICENSE`) because the hackathon
requires it — "Submissions must be original and MIT-compliant" is a
non-negotiable rule of the competition, not a choice made for this project.
Worth being direct about what that means in practice, since Spap intends to
keep using this agent after the hackathon if it performs well: MIT lets
*anyone*, including a commercial entity, copy, modify, and even sell this
exact code without paying or asking permission — the only obligation is
keeping the copyright notice. There is no way to submit to this hackathon
and keep the code private; the two are mutually exclusive by the rules.

Agreed plan, given that:
- After the hackathon, Spap keeps running his own private copy of this
  agent (a separate local/private clone, not the public repo) even though
  the public repo's history — everything committed during the hackathon
  window — stays public forever. Nothing about that history can be made
  private retroactively once submitted.
- Any real improvement developed *after* the hackathon that Spap wants to
  keep proprietary (a better strategy, a materially different risk model,
  etc.) goes into a new, separate, non-public repository — not committed
  here. This repo stays frozen as "the hackathon submission," not a living
  codebase for anything Spap later wants to protect.

## Status

*This section was stale until 24/08 evening — it still said "not yet run
end-to-end," found and corrected in a "cherche encore" pass after noticing
`PLAN_SPRINT.md` already documented a real run. Worth remembering: a status
paragraph that isn't updated when reality changes is exactly the kind of
silent code/doc gap this project exists to catch elsewhere — including in
itself.*

Zero real funds at risk — paper trading only, enforced in `config.py`.

**Already run end-to-end for real, on the DEV account** (`.env`, not the
dedicated hackathon account): CLI installed and verified, a real paper
option order was submitted and later closed via a real take-profit/stop-loss
check, and the hosted dashboard was visually confirmed in a real browser
showing that real data. See `PLAN_SPRINT.md`'s "Premier test réel réussi"
section for the exact order IDs and what was found and fixed along the way
(four real code/API mismatches, including one — the options-contracts
pagination bug — that would have silently refused every trade forever).

**Update, later on 24/08**: the multi-position controls above (sector cap,
data-quality gate, HALT switch, duplicate-order guard, consecutive-loss
breaker) and a batch of resilience fixes from later "cherche encore" passes
*were* then run for real against the live API, not just mocked. A real paper
option order filled (`2e7ba582-3784-4c80-8abb-d1e4eb0a79eb`, 2 puts
`SPY260831P00764000` at $4.69), `HALT` blocked new entries without blocking
an in-progress exit, the duplicate-order guard fired for real, and
`hindsight_guard` genuinely rejected XLK live. Five more real bugs turned up
in that same session's "cherche encore" passes, all one family — *the code
carefully protects the action, then treats its own trace of that action as
a detail* — see `PLAN_SPRINT.md` for the full list, in order, most recent
first.

**Not yet done, the real remaining gap**: the *dedicated* hackathon account
(`.env.hackathon`) has never been connected — everything above ran on dev,
on purpose, per the hackathon's own rule allowing any paper account during
development. And `monitor_exits.py` — the script meant to catch a stop-loss
between `agent.py`'s once-daily runs — is not actually running on schedule
yet: the `launchd` job is installed with the right cadence, but macOS's TCC
privacy protection on `~/Desktop` is blocking it from reading the script at
all. Fixing that needs a real person clicking through System Settings
(Full Disk Access), which is outside what this session can do.

Several terminal-handoff briefs exist from different points in the same
day (`BRIEF_TEST_AGENT_TERMINAL.md`, `BRIEF_GIT_DASHBOARD_PUBLICATION.md`,
`BRIEF_PUSH_GITHUB_PAGES.md`, `BRIEF_BACKTEST_REEL.md`,
`BRIEF_COMMIT_FIXES_ET_BACKTEST.md`, `BRIEF_MULTI_POSITION_ET_COMPARAISON.md`,
`BRIEF_VERIFICATION_FINALE_ET_COMMIT.md`) — **`BRIEF_DEBLOQUER_MONITOR_ET_KICKOFF.md`
is the current one**, waiting on the TCC fix above before the rest of its
checklist (28/08 account-switch procedure, real backtest re-run) can close
out. The others are earlier snapshots, all superseded.
See `PLAN_SPRINT.md` for the full day-by-day plan and complete history of
what was found and fixed.
