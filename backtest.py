"""Real backtest of the HV-rank strategy against real historical bars.

Why this exists: the agent's own honest disclosure (README, PLAN_SPRINT) was
"we verified the mechanism works, not that the underlying thesis makes
money" -- true, but unverified either way until now. This script actually
answers "is this strategy historically profitable, and by how much" using
the project's own scoring code (vol_strategy.py), not a new implementation
that could quietly disagree with what the live agent does.

Requires network access to Alpaca's data API via the CLI (alpaca_cli.py) --
same reason this can't run inside Cowork's sandbox as everything else that
touches the real API. Run from a real terminal:

    python backtest.py                      # default universe SPY,GLD,XLK,XLV
    python backtest.py --symbols SPY,GLD,XLK,XLV,QQQ

IMPORTANT, read before quoting any number from this script anywhere public:
the "proxy payoff" computed here (see vol_strategy._vol_strategy_returns'
docstring) is abs(next-day return) minus a cost term scaled by realized vol
at entry. It is a deliberate simplification used because Alpaca does not
expose historical option-IV data to backtest against -- NOT a real options
premium simulation. It ignores bid-ask spread, time decay (theta) between
entry and the next bar, and the actual strike/expiry chosen at trade time.
Treat every number below as "does the regime call have any historical
edge at all", not "this is what $976 in real premium would have returned".
Report both, honestly labeled, in the write-up -- don't quietly drop this
paragraph when it's time to make a slide.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import List, Optional

import alpaca_cli
import hindsight_guard
from vol_strategy import (
    CANDIDATE_HV_WINDOWS,
    MIN_TRADING_DAYS_FOR_SWEEP,
    Bar,
    _vol_strategy_returns,
    daily_returns,
    score_hv_window,
)

RESULTS_FILE = Path(__file__).parent / "BACKTEST_RESULTS.md"


def max_drawdown(cumulative: List[float]) -> float:
    """Largest peak-to-trough drop in the cumulative proxy-payoff curve.

    NOT an account drawdown, and the difference matters when this number is
    published: the curve is a running SUM of daily payoffs, not a compounded
    equity curve, so the figure is in payoff units and cannot be read as "the
    account fell X%". The internal field is named max_drawdown_proxy for that
    reason -- the report's column header used to drop the qualifier, which is
    the one place a reader would have met the number (fixed 24/08)."""
    if not cumulative:
        return 0.0
    peak = cumulative[0]
    worst = 0.0
    for v in cumulative:
        peak = max(peak, v)
        worst = min(worst, v - peak)
    return worst


def _top_n_share(trade_rets: List[float], n: int) -> Optional[float]:
    """What percentage of the cumulative payoff comes from the best n trade
    days. None when the total is <= 0 (the share would be meaningless, and
    inventing a number there is exactly the kind of thing this report must
    not do)."""
    total = sum(trade_rets)
    if not trade_rets or total <= 0:
        return None
    return round(100.0 * sum(sorted(trade_rets, reverse=True)[:n]) / total, 1)


def buy_and_hold_return(bars: List[Bar]) -> float:
    if len(bars) < 2 or bars[0].close == 0:
        return 0.0
    return (bars[-1].close - bars[0].close) / bars[0].close


def backtest_symbol(symbol: str, bars: List[Bar]) -> dict:
    result: dict = {"symbol": symbol, "bars_used": len(bars), "windows": {}}

    for window in CANDIDATE_HV_WINDOWS:
        strat_rets = _vol_strategy_returns(bars, window)
        trade_days = [r for r in strat_rets if r != 0.0]
        cumulative, running = [], 0.0
        for r in strat_rets:
            running += r
            cumulative.append(running)

        result["windows"][window] = {
            "total_days_scored": len(strat_rets),
            "trade_days": len(trade_days),
            "trade_frequency_pct": round(100 * len(trade_days) / len(strat_rets), 1) if strat_rets else 0.0,
            "cumulative_proxy_payoff": round(cumulative[-1], 4) if cumulative else 0.0,
            "win_rate_on_trade_days_pct": round(100 * sum(1 for r in trade_days if r > 0) / len(trade_days), 1) if trade_days else 0.0,
            "avg_payoff_per_trade": round(mean(trade_days), 5) if trade_days else 0.0,
            "max_drawdown_proxy": round(max_drawdown(cumulative), 4),
            # Share of the total payoff contributed by the best 5 trade days.
            # Computed and PUBLISHED because the headline number is meaningless
            # without it: a long-optionality rule is expected to earn on a few
            # large moves, so a positive total says little until you know how
            # few days carry it. Written into the report by the script rather
            # than added by hand afterwards -- a hand-written analysis in a
            # regenerated file was silently wiped twice before this (24/08).
            "top5_share_pct": _top_n_share(trade_days, 5),
        }

    # Replay what the live agent's own leak check would have picked, honestly
    # (same call agent.py makes) -- not a separate hand-picked "best window".
    def score_fn(window: int, split: str) -> float:
        return score_hv_window(window, split, bars)

    report = hindsight_guard.check_selection_leakage(CANDIDATE_HV_WINDOWS, score_fn, threshold=0.0)
    result["hindsight_guard_verdict"] = {
        "agrees": report.agrees,
        "full_winner": report.full_winner,
        "in_sample_winner": report.in_sample_winner,
        "summary": report.summary(),
    }

    result["buy_and_hold_return_pct"] = round(100 * buy_and_hold_return(bars), 2)
    return result


def format_report(results: List[dict]) -> str:
    lines = [
        "# Backtest results — HV-rank strategy vs real historical bars",
        "",
        f"*Generated {datetime.now(timezone.utc).isoformat()}. Proxy payoff, not real options P&L — see backtest.py's module docstring for exactly what is and isn't simulated.*",
        "",
    ]
    for r in results:
        lines.append(f"## {r['symbol']} ({r['bars_used']} bars used)")
        lines.append("")
        lines.append(
            f"*Buy-and-hold over the same bars: **{r['buy_and_hold_return_pct']}%**. "
            "🔴 This is NOT comparable to the payoff column below and must never be "
            "ranked against it: buy-and-hold is a compounded price return over every "
            "day of the period, while `cum. proxy payoff` is a SUM of daily "
            "`abs(return) - cost` payoffs on the minority of days the rule was in a "
            "position at all. Different quantities, different denominators. It is "
            "printed for context on what the underlying did, not as a benchmark to "
            "beat.*"
        )
        lines.append("")
        lines.append("| window (days) | trade days | freq | cum. proxy payoff | win rate on trades | avg payoff/trade | max drawdown (proxy units) |")
        lines.append("|---|---|---|---|---|---|---|")
        for w, d in r["windows"].items():
            lines.append(
                f"| {w} | {d['trade_days']}/{d['total_days_scored']} | {d['trade_frequency_pct']}% "
                f"| {d['cumulative_proxy_payoff']} | {d['win_rate_on_trade_days_pct']}% "
                f"| {d['avg_payoff_per_trade']} | {d['max_drawdown_proxy']} |"
            )
        conc = [
            f"{w}d: **{d['top5_share_pct']}%**"
            for w, d in r["windows"].items() if d.get("top5_share_pct") is not None
        ]
        if conc:
            lines.append("")
            lines.append(
                "🔴 **Concentration — share of each positive total earned on its best 5 trade "
                "days:** " + " · ".join(conc) + ". *A share ABOVE 100% is not an error: it "
                "means those five days earned more than the entire net result, i.e. every "
                "other trade day combined lost money.* A long-optionality rule is *expected* to "
                "earn on a handful of large moves, so this is the payoff's signature rather "
                "than an anomaly — but it means a positive total built from ~100 trades does "
                "not distinguish an edge from luck, and that the omitted costs (spread, theta) "
                "would bite hardest on exactly what remains after those days are removed."
            )
        lines.append("")
        lines.append(f"**hindsight_guard verdict for this symbol:** {'agrees (no leak)' if r['hindsight_guard_verdict']['agrees'] else 'LEAK DETECTED'} — full-window winner: {r['hindsight_guard_verdict']['full_winner']} days, in-sample winner: {r['hindsight_guard_verdict']['in_sample_winner']} days.")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default="SPY,GLD,XLK,XLV", help="comma-separated symbols")
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    results = []
    for symbol in symbols:
        # try/except added 24/08, "cherche encore" -- same unguarded pattern
        # just found and fixed in agent.py's live entry loop (see
        # PLAN_SPRINT.md, 16th pass): alpaca_cli.get_daily_bars() can raise
        # DataQualityError (stale/implausible bars) or AlpacaCLIError (a CLI
        # hiccup) for any ONE symbol. Unguarded, that would crash this whole
        # script -- losing the results already computed for every symbol
        # processed before it, and RESULTS_FILE would never get written at
        # all, even partially. Same "one bad symbol shouldn't cost the whole
        # report" principle, just never applied to this offline script when
        # it was first written.
        try:
            print(f"Fetching {MIN_TRADING_DAYS_FOR_SWEEP}+ trading days of bars for {symbol}...")
            bars = alpaca_cli.get_daily_bars(symbol)
            print(f"  got {len(bars)} bars, backtesting {len(CANDIDATE_HV_WINDOWS)} windows...")
            results.append(backtest_symbol(symbol, bars))
        except Exception as e:
            print(f"  ERROR backtesting {symbol}: {type(e).__name__}: {e} -- skipping this symbol, continuing with the rest")

    if not results:
        print("\nNo symbol produced a usable backtest result -- nothing to report.")
        return

    report = format_report(results)
    RESULTS_FILE.write_text(report)
    print(f"\nWrote {RESULTS_FILE}")
    print(report)


if __name__ == "__main__":
    main()
