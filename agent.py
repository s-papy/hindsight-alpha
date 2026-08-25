"""Hindsight Alpha — an options-trading agent that refuses to trust its own
parameter selection until it's checked for hindsight leakage.

Flow, per symbol in the universe (default SPY, GLD, XLK, XLV — see "Why
these four symbols" below):
  1. Fetch daily bars for the underlying.
  2. Sweep candidate historical-volatility windows (vol_strategy.CANDIDATE_HV_WINDOWS)
     for a "buy optionality when realized vol is cheap relative to its own
     history" rule — see vol_strategy.py for why this is HV rank, not IV
     rank, and what the backtest payoff proxy does and doesn't model.
  3. Run hindsight_guard.check_selection_leakage: does the window that wins
     on the FULL bar history still win when scored only on what was knowable
     before the most recent IN_SAMPLE_HOLDOUT_DAYS?
  4. If the two windows disagree (or nothing clears the Sharpe bar in-sample),
     this symbol is skipped for today — an agent that catches its own
     look-ahead bias instead of trading on it, not a bug.
  5. If they agree, check today's volatility regime with the vetted window.
     If it's not cheap, this symbol is skipped (no edge today, not a
     hindsight problem). If it is cheap, pick a direction with a short-term
     momentum tiebreaker and find a near-the-money option contract.

Before any of that, step 0.5 manages existing positions: risk_gates.manage_exits()
closes anything that's hit +50% (take-profit) or -50% (stop-loss) on
unrealized P&L, independent of whether a new entry looks good today —
position management isn't conditional on today's signal.

Since 24/08, EVERY symbol that clears steps 2-5 is attempted, not just the
first one — the agent can hold several positions at once now. Each attempt
still goes through risk_gates.check_gates(underlying, contract), which
enforces, per Spap's explicit direction ("plusieurs symboles différents...
jamais tous les mêmes, œuf dans le même panier"):
  - never two open positions on the same underlying at once;
  - a hard cap on the number of concurrent positions (risk_gates.MAX_OPEN_POSITIONS);
  - a per-trade cap of 1% of equity (risk_gates.MAX_RISK_PCT_PER_TRADE);
  - a TOTAL cap of 3% of equity committed across ALL open positions combined
    (risk_gates.MAX_TOTAL_RISK_PCT) — so a second and third position shrink
    the room left for further trades, they don't each get their own fresh 1%.
  - the weekly -3% drawdown lock (risk_gates.WEEKLY_LOSS_LOCK_PCT) already
    compares total account equity to the recorded starting equity, so it
    was already measuring combined drawdown across all positions, not a
    single isolated one — nothing needed to change there.
So up to MAX_OPEN_POSITIONS positions can be open at once, each on a
different underlying, with combined risk capped at 3% of equity regardless
of how many are open.

Why these four symbols, not just SPY: with three independent "no" gates
(hindsight check, volatility regime, risk gates) stacked on a single
low-volatility symbol like SPY, a genuinely realistic outcome is zero trades
across the entire hackathon week — intellectually honest, but the judging
explicitly includes "P&L Performance," and an agent that never acts has
nothing to show there or in the demo video. The universe used to be three
broad-market ETFs (SPY, QQQ, IWM) that are highly correlated with each other
(same macro driver, same days tend to be cheap/expensive vol for all three)
— diversifying the number of *chances* per day without diversifying the
*risk*. Since 24/08 the universe spans genuinely different sectors instead:
SPY (broad market anchor), GLD (gold/commodities), XLK (technology), XLV
(healthcare/pharma) — all deep, liquid, optionable ETFs, chosen over single
stocks for tighter spreads and safer sizing during a live hackathon week.
If two of these ever end up in open positions at once, they're exposed to
different macro drivers, not the same trade twice under different tickers.

All Alpaca calls go through alpaca_cli.py, a subprocess wrapper around
Alpaca's official CLI (github.com/alpacahq/cli) — not the alpaca-py SDK.
See alpaca_cli.py's module docstring for why: it's the hackathon's explicit
"MCP or CLI" requirement, and Alpaca's own docs recommend the CLI over the
MCP server for exactly this shape of agent (one command per invocation,
then exit — not a persistent AI-host session).

Run: python agent.py [--symbols SPY,GLD,XLK,XLV] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from typing import Optional

import alpaca_cli
import config
import decision_log
import risk_gates
from hindsight_guard import check_selection_leakage
from vol_strategy import (
    CANDIDATE_HV_WINDOWS,
    CHEAP_VOL_PERCENTILE,
    direction_tiebreak,
    score_hv_window,
    today_regime,
)

DEFAULT_UNIVERSE = ["SPY", "GLD", "XLK", "XLV"]  # broad market, commodities, tech, pharma/healthcare — not all the same eggs in one basket


@dataclass
class SymbolVerdict:
    symbol: str
    tradeable: bool
    reason: str
    direction: Optional[int] = None
    last_close: Optional[float] = None  # already fetched in evaluate_symbol; passed to
    # find_near_the_money_contract so it doesn't re-spawn a bars call for the same symbol


def evaluate_symbol(symbol: str, sharpe_threshold: float) -> SymbolVerdict:
    """Runs the full sweep -> hindsight_guard -> regime check for one symbol.
    Never touches risk_gates or submits anything — that happens once, in
    main(), only for whichever symbol (if any) comes back tradeable first.

    Any exception raised while evaluating THIS symbol (a transient API
    hiccup on `data bars`, an option-chain lookup failure, too few bars for
    a window, etc.) is caught here and turned into a "skip" verdict rather
    than left to propagate. Without this, one bad symbol out of the universe
    would crash the whole run via main()'s top-level try/except -- silently
    throwing away verdicts already computed for the other symbols and
    undermining the entire point of evaluating a universe instead of just
    SPY (see the module docstring: multiple chances per day to avoid a
    zero-trade week). A single flaky symbol should cost that one symbol's
    chance today, not the whole day's chance across all three."""
    print(f"\n--- {symbol} ---")
    try:
        bars = alpaca_cli.get_daily_bars(symbol)
        print(f"  got {len(bars)} bars")

        def score_fn(window: int, split: str) -> float:
            return score_hv_window(window, split, bars)

        report = check_selection_leakage(CANDIDATE_HV_WINDOWS, score_fn, threshold=sharpe_threshold)
        print(f"  hindsight_guard: {'OK' if report.agrees else 'LEAK DETECTED'} (winner: {report.full_winner})")

        if not report.agrees:
            return SymbolVerdict(symbol, False, "hindsight_guard: winning HV window doesn't hold up in-sample")

        vetted_window = report.full_winner
        is_cheap, hv_rank = today_regime(bars, vetted_window)
        print(f"  HV window={vetted_window}d, today's HV rank={hv_rank:.1f} (need < {CHEAP_VOL_PERCENTILE})")

        if not is_cheap:
            return SymbolVerdict(symbol, False, f"volatility not cheap today (HV rank {hv_rank:.1f})")

        signal = direction_tiebreak(bars)
        return SymbolVerdict(symbol, True, "cheap-vol regime confirmed, hindsight_guard clean",
                             direction=signal, last_close=bars[-1].close if bars else None)
    except Exception as e:
        print(f"  ERROR evaluating {symbol}: {type(e).__name__}: {e} -- skipping this symbol today")
        return SymbolVerdict(symbol, False, f"error evaluating symbol: {type(e).__name__}: {e}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--symbols",
        default=",".join(DEFAULT_UNIVERSE),
        help="comma-separated underlying symbols to evaluate, in priority order",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="run the full pipeline but never submit an order, even if a symbol is vetted",
    )
    parser.add_argument(
        "--sharpe-threshold",
        type=float,
        default=0.0,
        help="minimum in-sample Sharpe a window must clear to be trusted",
    )
    parser.add_argument(
        "--skip-market-check",
        action="store_true",
        help="skip the market-open check (useful for offline/dry-run testing of the rest of the pipeline)",
    )
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    record: dict = {"dry_run": args.dry_run, "symbols": symbols, "outcome": "unknown"}
    try:
        _run(args, symbols, record)
    except Exception as e:
        record["outcome"] = "error"
        record["error"] = f"{type(e).__name__}: {e}"
        raise
    finally:
        # A logging failure must not (a) destroy the only trace of a run that
        # really placed an order, nor (b) displace a genuine error as the one
        # that surfaces. Found 24/08, fourth "cherche encore" pass, following
        # the same pattern as the other four fixed today.
        #
        # Measured, not assumed:
        #   - order placed + log_run() raises -> the whole run exited with the
        #     logging error and decision_log.jsonl got NOTHING. The order
        #     exists at Alpaca; the agent's own decision log, and therefore
        #     the public dashboard, has no record of it.
        #   - _run() raises a real error AND log_run() raises -> the logging
        #     error is what surfaces. The original IS still reachable via
        #     __context__ (verified -- an earlier version of this note claimed
        #     it was lost, which was wrong: that came from how the test raised
        #     the exception, not from this code). So this half is cosmetic,
        #     not data loss -- but a traceback headed by "disk full" instead of
        #     the actual failure is still the wrong thing to hand a human at
        #     2am.
        #
        # Dumping the record to stdout on failure means the trace survives
        # wherever stdout goes (launchd's log, a terminal, CI output) instead
        # of nowhere. Not re-raising from the finally lets a real error from
        # _run() propagate as itself.
        decision_log.log_run_or_dump(
            record,
            context="The run itself is unaffected -- any order submitted above is real.",
        )


def _run(args, symbols, record: dict) -> None:
    config.require_credentials()

    if not args.skip_market_check:
        print("[0] Checking market clock...")
        clock = alpaca_cli.get_clock()
        record["market_open"] = clock.get("is_open", False)
        if not clock.get("is_open", False):
            print(
                f"Market is closed (next open: {clock.get('next_open', '?')}). "
                "Options only trade during market hours — nothing to do today. Exiting cleanly."
            )
            record["outcome"] = "market_closed"
            return
    else:
        record["market_open"] = None

    print("[0.5] Managing existing positions (take-profit / stop-loss)...")
    if args.dry_run:
        print("  --dry-run set: not closing anything, but here's what a real run would see:")
    exit_actions = risk_gates.manage_exits(dry_run=args.dry_run)
    # exit_actions is a List[risk_gates.ExitAction] (structured, since 24/08)
    # -- .to_dict() for the record so json.dumps in decision_log doesn't choke
    # on a dataclass; the print loop below keeps using the objects directly,
    # since ExitAction.__str__ reproduces the exact original sentence.
    record["exit_actions"] = [a.to_dict() for a in exit_actions]
    for action in exit_actions:
        print(f"  {action}")

    halted, halt_reason = risk_gates.is_halted()
    if halted:
        print(f"\n[HALT] {halt_reason}")
        print("Manual pause active (HALT file present) -- not evaluating or opening any new position today. "
              "Exits above still ran; remove the HALT file to resume.")
        record["outcome"] = "halted"
        record["halt_reason"] = halt_reason
        return

    print(f"\n[1] Evaluating universe: {symbols}")
    verdicts = [evaluate_symbol(sym, args.sharpe_threshold) for sym in symbols]
    record["verdicts"] = [
        {"symbol": v.symbol, "tradeable": v.tradeable, "reason": v.reason, "direction": v.direction}
        for v in verdicts
    ]

    tradeable_verdicts = [v for v in verdicts if v.tradeable]

    print("\n[2] Summary:")
    for v in verdicts:
        marker = "TRADEABLE" if v.tradeable else "skip"
        print(f"  {v.symbol}: {marker} — {v.reason}")

    if not tradeable_verdicts:
        print("\nNo symbol in the universe cleared both gates today. No order submitted.")
        record["outcome"] = "no_edge"
        return

    if args.dry_run:
        print(f"\n--dry-run set: {len(tradeable_verdicts)} symbol(s) tradeable "
              f"({', '.join(v.symbol for v in tradeable_verdicts)}), but not looking up "
              "contracts or submitting orders.")
        record["outcome"] = "dry_run_tradeable"
        record["tradeable_symbols"] = [v.symbol for v in tradeable_verdicts]
        return

    # Every symbol that cleared steps 2-5 gets a real attempt, not just the
    # first — risk_gates.check_gates() is what actually decides how many of
    # these end up as orders (duplicate-underlying block, MAX_OPEN_POSITIONS,
    # and the shared 3%-of-equity total-exposure cap all apply across this
    # loop, so later attempts naturally get shrunk or blocked once earlier
    # ones in the same run have committed budget).
    #
    # committed_this_run / opened_this_run track what THIS run has already
    # spent, in memory -- passed into every check_gates() call after the
    # first. Needed because check_gates() re-reads open positions from the
    # live API each time, and a just-submitted paper order isn't guaranteed
    # to show up there instantly (order submit returns on acceptance, not
    # necessarily on fill). Without this, a second or third symbol in the
    # same run could pass the total-exposure/position-count checks as if
    # the earlier order(s) from this same run never happened.
    print(f"\n[3] Attempting entry for {len(tradeable_verdicts)} tradeable symbol(s): "
          f"{', '.join(v.symbol for v in tradeable_verdicts)}")
    trades = []
    orders_submitted = 0
    # Keyed by underlying, not a running total/count -- fixed 24/08, second
    # pass on this same-run tracking (see risk_gates.check_gates()'s
    # docstring): a running float/count always got added in full, even if
    # the live API happened to catch up on an earlier order before the next
    # symbol's check, which would have double-counted that position.
    # check_gates() now filters out underlyings it can already see live.
    committed_this_run_by_underlying: dict = {}
    opened_this_run_underlyings: set = set()
    for tradeable in tradeable_verdicts:
        direction_label = "bullish (call)" if tradeable.direction > 0 else "bearish (put)"
        print(f"\n-- {tradeable.symbol} ({direction_label}) --")
        trade_record: dict = {"symbol": tradeable.symbol, "direction": direction_label}

        # Wrapped in try/except -- found 24/08, "cherche encore": this loop
        # had NO per-symbol exception isolation, unlike evaluate_symbol()
        # above (see that function's docstring for the exact same rationale,
        # already written down there but never extended to this second loop
        # over the SAME universe). find_near_the_money_contract() ->
        # get_last_price() -> get_daily_bars() can raise DataQualityError
        # (control #63, added earlier this session) or AlpacaCLIError on a
        # transient API hiccup -- and so can check_gates() and
        # submit_paper_option_order(). Unguarded, any of those on ANY ONE
        # symbol mid-loop would propagate out of _run() entirely, hit only
        # main()'s top-level except, and: (1) skip every symbol still left
        # in tradeable_verdicts even if they had nothing wrong with them,
        # and (2) worse, never reach `record["trades"] = trades` below --
        # so even orders ALREADY submitted for earlier symbols in this same
        # run would vanish from decision_log.jsonl entirely, not just get
        # mislabeled. Same failure shape as the missing per-symbol isolation
        # this project explicitly designed AROUND in evaluate_symbol(), just
        # never carried over to this loop when it was rewritten for multiple
        # symbols. Not yet triggered for real -- found by re-reading, not by
        # a live crash.
        try:
            contract = alpaca_cli.find_near_the_money_contract(
                tradeable.symbol, tradeable.direction, spot=tradeable.last_close
            )
            trade_record["contract"] = contract
            if contract is None:
                print("  No matching option contract found (check market hours / symbol / expiry window).")
                trade_record["outcome"] = "no_contract_found"
                trades.append(trade_record)
                continue

            print(f"  Selected contract: {contract}")
            print("  Checking risk gates (duplicate underlying, sector cap, position cap, per-trade + total exposure cap, weekly loss lock)...")
            decision = risk_gates.check_gates(
                tradeable.symbol, contract,
                already_committed_this_run_by_underlying=committed_this_run_by_underlying,
                already_open_this_run_underlyings=opened_this_run_underlyings,
            )
            trade_record["risk_gate_reason"] = decision.reason
            print(f"    {decision.reason}")
            if not decision.allowed:
                print("  Risk gates blocked this trade. No order submitted.")
                trade_record["outcome"] = "risk_gate_blocked"
                trades.append(trade_record)
                continue

            order_id = alpaca_cli.submit_paper_option_order(contract, qty=decision.qty)

            # The order EXISTS from this line on. Everything below is
            # bookkeeping about an order that has already been placed, so
            # nothing below may be allowed to make this run behave as though
            # it hadn't been.
            #
            # These two accumulators move FIRST, before any call that can
            # raise -- found 24/08, "cherche encore", by reproducing it:
            # record_order_submitted() writes state.json, and a write failure
            # there (the same crash-mid-write scenario _load_state's
            # corruption handling was written for) used to jump straight to
            # this loop's `except`, skipping both updates. The order was
            # filled, but the NEXT symbol in the same run was then gated as
            # if that position did not exist -- committed={} and open=set()
            # instead of {'SPY': 950.0} / {'SPY'} -- so MAX_TOTAL_RISK_PCT,
            # MAX_SECTOR_EXPOSURE_PCT and MAX_OPEN_POSITIONS could all be
            # exceeded in aggregate during the very API-lag window these
            # accumulators exist to cover.
            #
            # Same shape as the manage_exits() fix earlier in this pass ("a
            # position really closed must never be reported as left open just
            # because the streak counter failed afterwards"), but on the
            # ENTRY path -- and unlike most isolation gaps found today, this
            # one failed on the DANGEROUS side: over-exposure, not a
            # needlessly refused trade.
            committed_this_run_by_underlying[tradeable.symbol.upper()] = decision.committed_dollars
            opened_this_run_underlyings.add(tradeable.symbol.upper())

            # Own try/except for the same reason: this is a state.json write,
            # it is the most likely thing here to fail, and its failure must
            # not be reported as "no order was placed".
            try:
                risk_gates.record_order_submitted(tradeable.symbol)
            except Exception as e:
                print(f"  WARNING: order {order_id} WAS submitted for {tradeable.symbol}, but recording it "
                      f"in state.json failed ({type(e).__name__}: {e}). The duplicate-order guard may not "
                      "block a rerun today -- check open positions before re-running.")
                trade_record["record_order_submitted_failed"] = f"{type(e).__name__}: {e}"

            print(f"  Paper order submitted (via `alpaca order submit`). qty={decision.qty} id={order_id}")
            trade_record["outcome"] = "order_submitted"
            trade_record["order_id"] = order_id
            trade_record["qty"] = decision.qty
            trades.append(trade_record)
            orders_submitted += 1
        except Exception as e:
            print(f"  ERROR attempting entry for {tradeable.symbol}: {type(e).__name__}: {e} -- skipping this symbol today")
            trade_record["outcome"] = "error"
            trade_record["error"] = f"{type(e).__name__}: {e}"
            trades.append(trade_record)
            continue

    record["trades"] = trades
    record["orders_submitted"] = orders_submitted
    if orders_submitted > 0:
        record["outcome"] = "order_submitted"
    else:
        # Aggregate outcome across every attempt today, for the top-level
        # dashboard badge -- pick the reason that actually applied instead
        # of defaulting to "risk_gate_blocked" when the real reason was
        # e.g. every symbol failing contract lookup (misleading otherwise:
        # a judge reading "blocked by risk gate" when no gate was ever
        # reached would be reading the wrong story).
        #
        # That handles every symbol sharing the SAME outcome -- but found
        # 25/08, "cherche encore", re-reading this exact block: the ELSE
        # branch still hard-coded "risk_gate_blocked" whenever outcomes
        # DIFFER across symbols, regardless of whether risk_gate_blocked was
        # even among them. Reproduced: trades = [no_contract_found, error]
        # (zero symbols actually reached a risk gate) still produced
        # record["outcome"] == "risk_gate_blocked" -- the exact same
        # misleading-badge failure this block's own comment says it exists
        # to prevent, just for the case nobody tested (multiple DIFFERENT
        # reasons, none of them risk_gate_blocked). docs/index.html's
        # outcomeBadge() would render the public dashboard's top-level badge
        # as "blocked by risk gate" on a day where no risk gate was ever
        # reached by anything. Each trade's own true reason is still shown
        # correctly in the per-trade detail line below the badge (see
        # renderTrade()) -- only the SUMMARY badge lied.
        #
        # Fixed honestly rather than picking a different single reason to
        # default to (any single choice among N different real reasons is
        # equally arbitrary and equally misleading): a heterogeneous set of
        # outcomes reports "mixed", which outcomeBadge() renders as a plain
        # muted badge with that literal label rather than crashing or
        # falling back silently -- verified against its `map[d.outcome] ||
        # ['badge-muted', d.outcome || 'unknown']` fallback.
        trade_outcomes = {t["outcome"] for t in trades}
        record["outcome"] = trade_outcomes.pop() if len(trade_outcomes) == 1 else "mixed"


if __name__ == "__main__":
    main()
