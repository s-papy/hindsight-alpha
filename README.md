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
`SPY,QQQ,IWM` — configurable via `--symbols`), not just one. With three
independent "no" gates stacked (hindsight check, volatility regime, risk
gates) on a single low-volatility symbol, a real risk was zero trades across
the whole hackathon week — honest, but the judging explicitly weighs "P&L
Performance," and a silent agent has nothing to show there or in the demo.
Testing several similarly-liquid symbols is the same honest gate applied
more times, not a loosened one; the first symbol that clears every gate is
the one traded, and `risk_gates.py`'s one-position cap stops any other
symbol from also trading that day. See `agent.evaluate_symbol()`.

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
6. Before submitting anything, `risk_gates.py` checks: is the market open
   (skips cleanly on weekends/holidays), is a position already open (never
   stacks a second one), does 1 contract fit inside a 1%-of-equity per-trade
   cap (sizes down or skips instead of trading blind), and has the account
   dropped more than 3% from its recorded starting equity this week (a
   sticky lock — once tripped, no more trades until state.json is reset).
   Only if every gate clears does it submit a **paper** market order.

### Risk gates

Required by the hackathon's one-page write-up ("risk gates" is one of the
three things it must cover) and, more importantly, because an agent that
can buy again every day with no cap on position count or capital at risk
isn't a trading agent — it's a liability generator with a good idea buried
inside it. See `risk_gates.py`:

- **Entry side**: one open position at a time, a 1% of equity per-trade cap
  (sized from the contract's live ask price, or skipped if even 1 contract
  doesn't fit), and a 3% weekly drawdown lock that persists in `state.json`
  across days so a bad stretch actually stops the agent instead of letting
  it keep re-entering.
- **Exit side**: `manage_exits()` runs first, before any new-entry
  evaluation, and closes any open position at +50% (take-profit) or -50%
  (stop-loss) on unrealized P&L — added after noticing the first draft only
  ever bought and never managed a position afterward, which would have left
  every trade unrealized (paper) until the judging window ended.

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
- `risk_gates.py` — one-position cap, per-trade risk cap, weekly drawdown
  lock. State persists in `state.json` (gitignored, created on first run).
- `decision_log.py` — appends one JSON record per run to `decision_log.jsonl`
  (committed, not gitignored — it's evidence of what the agent decided and
  why, every day of the hackathon, not a secret).
- `publish_dashboard.py` — snapshots the live account, positions, and recent
  decisions into `docs/data.json` for the hosted dashboard.
- `docs/index.html` — the dashboard itself: a single static HTML page, no
  build step, no framework, fetches `./data.json` and renders it. Meant to
  be served by GitHub Pages from this repo's `docs/` folder — see "Hosted
  dashboard" below.

## Hosted dashboard

Required by the submission ("Demo application platform", "Application
URL"). Hosting choice: **GitHub Pages serving `docs/`**, not a separate
server — same pattern already used for another of Spap's projects
(SNIPER's D31 dashboard). The reasoning: the public page never needs to see
an API key. `publish_dashboard.py` runs locally (wherever `agent.py` runs,
with real credentials in `.env`), writes a plain JSON snapshot, and that
snapshot — not a live connection — is what gets committed and served.
Nothing publicly reachable ever touches Alpaca directly.

Setup (once, in a real terminal — see `BRIEF_TEST_AGENT_TERMINAL.md`):

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

Checked without a live browser (the dev sandbox that wrote this can't open
local files in Chrome): the HTML parses with no unclosed tags, the
dashboard's embedded JS has valid syntax, and every field the JS reads
(`account.equity`, `position.unrealized_plpc`, `decision.chosen_symbol`,
etc.) was cross-checked line-by-line against what `publish_dashboard.py`
and `agent.py`'s decision-log record actually produce — they match. Not
the same as seeing it render; worth a quick look in an actual browser
before recording the demo video.
- `test_connection.py` — run first; confirms CLI install + `.env` + network
  access all work.
- `config.py` — loads `.env`, hard-refuses to run against anything that
  looks like a live-trading configuration.
- `alpaca_client.py`, `momentum_strategy.py` — dead code from earlier
  drafts (alpaca-py SDK version, TSMOM strategy version). Left in place
  because Cowork's sandbox can't delete files in this shared folder;
  nothing imports them. Safe to delete by hand.

## Status

Zero real funds at risk — paper trading only, enforced in `config.py`.
Not yet run end-to-end (blocked on both network access and CLI install from
the dev sandbox); next step is running `test_connection.py` and
`agent.py --dry-run` from a real terminal to confirm the pipeline works
against live Alpaca data before recording the hackathon demo video. See
`PLAN_SPRINT.md` for the full day-by-day plan and `BRIEF_TEST_AGENT_TERMINAL.md`
for the terminal handoff.
