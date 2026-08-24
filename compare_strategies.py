"""Real, side-by-side comparison of the two strategy families this repo
contains: vol_strategy.py (HV-rank optionality, what the live agent
actually trades) vs momentum_strategy.py (TSMOM, written earlier as a
demonstration of the same hindsight_guard leak-check pattern but never
wired into agent.py or backtested against real data until now).

Why this exists: Spap's own words, 24/08 — "ajouter au prochain brief
terminal si tu veux vraiment la meilleure stratégie, pas juste celle qui
raconte la meilleure histoire aux juges." The HV-rank strategy is the one
in the pitch because it's options-native (a volatility-regime call, not
"is a stock going up") -- a better STORY for an options hackathon. This
script exists to check, on the same real bars, whether it also has the
better DATA, or whether momentum quietly has a more robust edge that's
being passed over for narrative reasons. Report whichever one actually
wins here, honestly, even if it undercuts the pitch.

CRITICAL CAVEAT, read before comparing a single number across the two
tables below: they are NOT the same unit.
  - vol_strategy's payoff is a PROXY for options P&L (abs next-day return
    minus a vol-scaled cost term), and it is FLAT (0) on most days --
    it only "trades" when HV rank says optionality is cheap. See
    vol_strategy.py's docstring for the full honesty note on what this
    does and doesn't model.
  - momentum_strategy's payoff is a REAL daily stock return (signal *
    next-day return) -- directly investable, no proxy. It also trades
    EVERY day (always long or short, never flat).
A momentum cumulative return of +40% and a vol_strategy cumulative proxy
payoff of +0.10 are not comparable magnitudes by construction. What IS
comparable, and what this script reports side by side: (a) does each
family's hindsight_guard check agree (no leak) or disagree (leak) on each
symbol, (b) win rate on days each strategy actually took a position,
(c) Sharpe of the vetted window/lookback's in-sample score -- the same
statistic the live leak-check itself uses to decide "is this trustworthy",
so it's the fairest single number to put side by side.

Run from a real terminal (same network requirement as backtest.py):
    python compare_strategies.py                    # default universe
    python compare_strategies.py --symbols SPY,GLD,XLK,XLV
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import List

import alpaca_cli
import hindsight_guard
from vol_strategy import (
    CANDIDATE_HV_WINDOWS,
    MIN_TRADING_DAYS_FOR_SWEEP,
    _vol_strategy_returns,
    score_hv_window,
)
from momentum_strategy import (
    CANDIDATE_LOOKBACKS,
    _tsmom_returns,
    score_lookback,
)

RESULTS_FILE = Path(__file__).parent / "STRATEGY_COMPARISON.md"


def _win_rate(rets: List[float]) -> float:
    nonzero = [r for r in rets if r != 0.0]
    if not nonzero:
        return 0.0
    return 100 * sum(1 for r in nonzero if r > 0) / len(nonzero)


def compare_symbol(symbol: str, bars) -> dict:
    result: dict = {"symbol": symbol, "bars_used": len(bars)}

    # --- vol_strategy: same leak-check the live agent runs ---
    def vol_score_fn(window: int, split: str) -> float:
        return score_hv_window(window, split, bars)

    vol_report = hindsight_guard.check_selection_leakage(CANDIDATE_HV_WINDOWS, vol_score_fn, threshold=0.0)
    vol_window = vol_report.full_winner
    vol_rets = _vol_strategy_returns(bars, vol_window)
    vol_trade_rets = [r for r in vol_rets if r != 0.0]
    result["vol_strategy"] = {
        "vetted_window_days": vol_window,
        "hindsight_guard_agrees": vol_report.agrees,
        "in_sample_sharpe_of_winner": round(score_hv_window(vol_window, "in_sample", bars), 3),
        "trade_days": len(vol_trade_rets),
        "total_days_scored": len(vol_rets),
        "win_rate_pct": round(_win_rate(vol_rets), 1),
        "avg_payoff_per_trade": round(mean(vol_trade_rets), 5) if vol_trade_rets else 0.0,
        "cumulative_proxy_payoff": round(sum(vol_rets), 4),
    }

    # --- momentum_strategy: same leak-check pattern, real returns ---
    def mom_score_fn(lookback: int, split: str) -> float:
        return score_lookback(lookback, split, bars)

    mom_report = hindsight_guard.check_selection_leakage(CANDIDATE_LOOKBACKS, mom_score_fn, threshold=0.0)
    mom_lookback = mom_report.full_winner
    mom_rets = _tsmom_returns(bars, mom_lookback)
    result["momentum_strategy"] = {
        "vetted_lookback_days": mom_lookback,
        "hindsight_guard_agrees": mom_report.agrees,
        "in_sample_sharpe_of_winner": round(score_lookback(mom_lookback, "in_sample", bars), 3),
        "trade_days": len(mom_rets),  # always "in the market" -- every day is a trade day
        "win_rate_pct": round(_win_rate(mom_rets), 1),
        "avg_return_per_day": round(mean(mom_rets), 5) if mom_rets else 0.0,
        "cumulative_return_pct": round(100 * sum(mom_rets), 2),
    }

    return result


def format_report(results: List[dict]) -> str:
    lines = [
        "# Strategy comparison — vol_strategy (HV-rank) vs momentum_strategy (TSMOM)",
        "",
        f"*Generated {datetime.now(timezone.utc).isoformat()}, real bars via alpaca_cli.get_daily_bars.*",
        "",
        "**Read compare_strategies.py's module docstring before quoting any single "
        "number below** — the two families' payoffs are different units (options "
        "proxy vs real stock return) and are not directly summable or comparable "
        "as raw magnitudes. What IS comparable per symbol: hindsight_guard "
        "agreement (is either one's winner an actual leak), and the in-sample "
        "Sharpe of each vetted parameter (same statistic, same holdout window "
        "length, same computation) — that's the fairest apples-to-apples number.",
        "",
        "| symbol | vol_strategy: window | agrees? | in-sample Sharpe | win rate | momentum: lookback | agrees? | in-sample Sharpe | win rate |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        v, m = r["vol_strategy"], r["momentum_strategy"]
        lines.append(
            f"| {r['symbol']} | {v['vetted_window_days']}d | "
            f"{'yes' if v['hindsight_guard_agrees'] else '**LEAK**'} | "
            f"{v['in_sample_sharpe_of_winner']} | {v['win_rate_pct']}% | "
            f"{m['vetted_lookback_days']}d | "
            f"{'yes' if m['hindsight_guard_agrees'] else '**LEAK**'} | "
            f"{m['in_sample_sharpe_of_winner']} | {m['win_rate_pct']}% |"
        )
    lines.append("")
    lines.append("## Detail per symbol")
    lines.append("")
    for r in results:
        v, m = r["vol_strategy"], r["momentum_strategy"]
        lines.append(f"### {r['symbol']} ({r['bars_used']} bars used)")
        lines.append("")
        lines.append(
            f"- **vol_strategy** — vetted window {v['vetted_window_days']}d, "
            f"hindsight_guard {'agrees (no leak)' if v['hindsight_guard_agrees'] else 'LEAK DETECTED'}, "
            f"in-sample Sharpe {v['in_sample_sharpe_of_winner']}, "
            f"{v['trade_days']}/{v['total_days_scored']} days traded ({v['win_rate_pct']}% win rate on those days), "
            f"cumulative proxy payoff {v['cumulative_proxy_payoff']}."
        )
        lines.append(
            f"- **momentum_strategy** — vetted lookback {m['vetted_lookback_days']}d, "
            f"hindsight_guard {'agrees (no leak)' if m['hindsight_guard_agrees'] else 'LEAK DETECTED'}, "
            f"in-sample Sharpe {m['in_sample_sharpe_of_winner']}, "
            f"{m['trade_days']} days traded (always in the market), {m['win_rate_pct']}% win rate, "
            f"cumulative return {m['cumulative_return_pct']}%."
        )
        lines.append("")
    lines.append(
        "## Honest verdict (fill in after running this against real data — do not "
        "pre-write the conclusion)"
    )
    lines.append("")
    lines.append(
        "Compare the in-sample-Sharpe-of-winner column across both families. "
        "Whichever is consistently higher AND has hindsight_guard agreement across "
        "more symbols has the more robust vetted edge on this data — trade that "
        "one, or say plainly in the write-up if the options-native story "
        "(vol_strategy) was kept despite momentum scoring better, and why."
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", default="SPY,GLD,XLK,XLV", help="comma-separated symbols")
    args = parser.parse_args()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    results = []
    for symbol in symbols:
        # try/except added 24/08, "cherche encore" -- same fix as backtest.py
        # and agent.py's live entry loop today: a single symbol's
        # DataQualityError or AlpacaCLIError from get_daily_bars() shouldn't
        # take down the whole comparison and lose every symbol already
        # scored before it.
        try:
            print(f"Fetching {MIN_TRADING_DAYS_FOR_SWEEP}+ trading days of bars for {symbol}...")
            bars = alpaca_cli.get_daily_bars(symbol)
            print(f"  got {len(bars)} bars, scoring both strategy families...")
            results.append(compare_symbol(symbol, bars))
        except Exception as e:
            print(f"  ERROR comparing {symbol}: {type(e).__name__}: {e} -- skipping this symbol, continuing with the rest")

    if not results:
        print("\nNo symbol produced a usable comparison -- nothing to report.")
        return

    report = format_report(results)
    RESULTS_FILE.write_text(report)
    print(f"\nWrote {RESULTS_FILE}")
    print(report)


if __name__ == "__main__":
    main()
