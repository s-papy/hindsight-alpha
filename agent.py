"""Hindsight Alpha — an options-trading agent that refuses to trust its own
parameter selection until it's checked for hindsight leakage.

Flow, per symbol in the universe (default SPY, QQQ, IWM — see "Why a
universe" below):
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

The first symbol in the universe that clears steps 2-5 is the one traded
(subject to risk_gates.py, checked once, before that single order). Once one
symbol has an open position, risk_gates.has_open_option_position() blocks
any further symbol from also trading that day — the universe exists to
raise the odds that *something* trades, not to open multiple positions.

Why a universe, not just SPY: with three independent "no" gates (hindsight
check, volatility regime, risk gates) stacked on a single low-volatility
symbol like SPY, a genuinely realistic outcome is zero trades across the
entire hackathon week — intellectually honest, but the judging explicitly
includes "P&L Performance," and an agent that never acts has nothing to
show there or in the demo video. Testing a short list of similarly liquid,
optionable ETFs (SPY, QQQ, IWM) each day is the same honest gate applied
more times, not a loosened one.

All Alpaca calls go through alpaca_cli.py, a subprocess wrapper around
Alpaca's official CLI (github.com/alpacahq/cli) — not the alpaca-py SDK.
See alpaca_cli.py's module docstring for why: it's the hackathon's explicit
"MCP or CLI" requirement, and Alpaca's own docs recommend the CLI over the
MCP server for exactly this shape of agent (one command per invocation,
then exit — not a persistent AI-host session).

Run: python agent.py [--symbols SPY,QQQ,IWM] [--dry-run]
"""

from __future__ import annotations

import argparse
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

DEFAULT_UNIVERSE = ["SPY", "QQQ", "IWM"]


@dataclass
class SymbolVerdict:
    symbol: str
    tradeable: bool
    reason: str
    direction: Optional[int] = None


def evaluate_symbol(symbol: str, sharpe_threshold: float) -> SymbolVerdict:
    """Runs the full sweep -> hindsight_guard -> regime check for one symbol.
    Never touches risk_gates or submits anything — that happens once, in
    main(), only for whichever symbol (if any) comes back tradeable first."""
    print(f"\n--- {symbol} ---")
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
    return SymbolVerdict(symbol, True, "cheap-vol regime confirmed, hindsight_guard clean", direction=signal)


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
        decision_log.log_run(record)


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
    record["exit_actions"] = exit_actions
    for action in exit_actions:
        print(f"  {action}")

    print(f"\n[1] Evaluating universe: {symbols}")
    verdicts = [evaluate_symbol(sym, args.sharpe_threshold) for sym in symbols]
    record["verdicts"] = [
        {"symbol": v.symbol, "tradeable": v.tradeable, "reason": v.reason, "direction": v.direction}
        for v in verdicts
    ]

    tradeable = next((v for v in verdicts if v.tradeable), None)

    print("\n[2] Summary:")
    for v in verdicts:
        marker = "TRADEABLE" if v.tradeable else "skip"
        print(f"  {v.symbol}: {marker} — {v.reason}")

    if tradeable is None:
        print("\nNo symbol in the universe cleared both gates today. No order submitted.")
        record["outcome"] = "no_edge"
        return

    direction_label = "bullish (call)" if tradeable.direction > 0 else "bearish (put)"
    print(f"\nTrading {tradeable.symbol}, direction: {direction_label}")
    record["chosen_symbol"] = tradeable.symbol
    record["direction"] = direction_label

    if args.dry_run:
        print("--dry-run set: not looking up a contract or submitting an order.")
        record["outcome"] = "dry_run_tradeable"
        return

    contract = alpaca_cli.find_near_the_money_contract(tradeable.symbol, tradeable.direction)
    record["contract"] = contract
    if contract is None:
        print("No matching option contract found (check market hours / symbol / expiry window).")
        record["outcome"] = "no_contract_found"
        return

    print(f"Selected contract: {contract}")
    print("[3] Checking risk gates (open positions, per-trade cap, weekly loss lock)...")
    decision = risk_gates.check_gates(contract)
    record["risk_gate_reason"] = decision.reason
    print(f"  {decision.reason}")
    if not decision.allowed:
        print("Risk gates blocked this trade. No order submitted.")
        record["outcome"] = "risk_gate_blocked"
        return

    order_id = alpaca_cli.submit_paper_option_order(contract, qty=decision.qty)
    print(f"Paper order submitted (via `alpaca order submit`). qty={decision.qty} id={order_id}")
    record["outcome"] = "order_submitted"
    record["order_id"] = order_id
    record["qty"] = decision.qty


if __name__ == "__main__":
    main()
