"""Historical-volatility-rank strategy: buy optionality (a call or a put)
when the underlying's realized volatility is cheap relative to its own
recent history, skip when it's already expensive.

Honesty note on what this is and isn't: Alpaca's market data does not expose
a historical time series of *implied* volatility (option IV) that a backtest
could sweep over — only a live snapshot of the current option chain's
greeks. So instead of "IV rank", this uses **realized/historical volatility
rank (HV rank)** computed purely from the underlying's daily closes, which
is a standard practical proxy: cheap realized vol tends to precede cheap
option premiums, and vice versa. Anyone reading this code or the pitch deck
should see that distinction, not a claim of using real option IV history.

The backtest payoff is also a deliberate simplification, not a Black-Scholes
options-pricing model: on any day where HV rank was low at entry, the proxy
reward is the next day's absolute return (the actual payoff shape of owning
optionality — you profit from the *size* of the move, not its direction)
minus a cost term proportional to the HV level at entry (options cost more
when volatility is already elevated; here it's ~always low when we'd enter,
but the term is kept so the score isn't free money by construction). This
keeps the whole sweep computable from stock bars only — the same reliable,
historically-available data source used everywhere else in this agent — and
is honestly documented as a proxy rather than a real premium calculation.

This mirrors momentum_strategy.py's pattern exactly (candidate windows,
full-vs-in-sample scoring for hindsight_guard) but is options-native: the
decision to trade is driven by a volatility regime, not just direction.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import List, Sequence

IN_SAMPLE_HOLDOUT_DAYS = 20  # bars withheld from "in_sample" scoring
CANDIDATE_HV_WINDOWS = [10, 20, 30, 60, 90]  # trading days used to compute realized vol
CHEAP_VOL_PERCENTILE = 30  # enter only when HV rank falls below this
RANK_LOOKBACK_DAYS = 252  # trailing window used to rank "today's" HV against its own history
COST_MULTIPLIER = 1.0  # simplifying stand-in for "premium scales with vol at entry"

# How many trading days of bars the caller (alpaca_cli.get_daily_bars) needs
# to fetch for every candidate window to get a real, non-empty score. Each
# candidate needs RANK_LOOKBACK_DAYS of rolling-vol history *before* the
# scoring loop can start, plus its own window consumed computing that
# rolling vol in the first place — so the largest candidate window is the
# binding constraint. +250 trading days on top so every candidate gets a
# meaningful sample size (roughly a year's worth of usable score points),
# not just the bare minimum to be non-empty. A previous version of this
# agent fetched only 250 calendar-adjusted trading days by default, which
# silently starved the two largest candidates (60, 90) of any data at all
# (0 usable samples) and left the rest with as few as 8 — caught by testing
# this exact math, not by inspection.
MIN_TRADING_DAYS_FOR_SWEEP = RANK_LOOKBACK_DAYS + max(CANDIDATE_HV_WINDOWS) + 250


@dataclass
class Bar:
    close: float


def daily_returns(bars: Sequence[Bar]) -> List[float]:
    closes = [b.close for b in bars]
    return [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes))
        if closes[i - 1] != 0
    ]


def _sharpe(returns: Sequence[float]) -> float:
    if len(returns) < 2:
        return 0.0
    sd = pstdev(returns)
    if sd == 0:
        return 0.0
    return (mean(returns) / sd) * (252 ** 0.5)  # annualized, daily bars


def _realized_vol(returns: Sequence[float]) -> float:
    """Annualized realized volatility over the given return window."""
    if len(returns) < 2:
        return 0.0
    return pstdev(returns) * (252 ** 0.5)


def _hv_series(returns: Sequence[float], window: int) -> List[float]:
    """Rolling realized vol at each point in time (index i = vol computed
    from returns[i-window:i]). Length = len(returns) - window."""
    return [_realized_vol(returns[i - window:i]) for i in range(window, len(returns))]


def _percentile_rank(value: float, history: Sequence[float]) -> float:
    if not history:
        return 50.0
    below = sum(1 for h in history if h <= value)
    return 100.0 * below / len(history)


def _vol_strategy_returns(bars: Sequence[Bar], window: int) -> List[float]:
    """Backtest the 'buy optionality when HV rank is cheap' rule over the
    given bars. Returns the resulting daily proxy-payoff series."""
    rets = daily_returns(bars)
    hv = _hv_series(rets, window)
    strat_rets = []

    for i in range(RANK_LOOKBACK_DAYS, len(hv) - 1):
        history = hv[max(0, i - RANK_LOOKBACK_DAYS):i]
        rank = _percentile_rank(hv[i], history)
        if rank < CHEAP_VOL_PERCENTILE:
            next_day_ret_index = window + i + 1  # map hv-series index back into rets
            if next_day_ret_index >= len(rets):
                continue
            payoff = abs(rets[next_day_ret_index]) - COST_MULTIPLIER * hv[i] / (252 ** 0.5)
            strat_rets.append(payoff)
        else:
            strat_rets.append(0.0)  # flat: regime says options are not cheap, sit out

    return strat_rets


def score_hv_window(window: int, split: str, bars: Sequence[Bar]) -> float:
    """score_fn for hindsight_guard.check_selection_leakage.

    split="full"       -> Sharpe computed using every bar fetched.
    split="in_sample"   -> Sharpe computed using every bar except the most
                            recent IN_SAMPLE_HOLDOUT_DAYS — what would have
                            been knowable before "today".
    """
    if split == "full":
        usable_bars = bars
    elif split == "in_sample":
        cutoff = max(0, len(bars) - IN_SAMPLE_HOLDOUT_DAYS)
        usable_bars = bars[:cutoff]
    else:
        raise ValueError(f"unknown split: {split!r}")

    strat_rets = _vol_strategy_returns(usable_bars, window)
    return _sharpe(strat_rets)


def today_regime(bars: Sequence[Bar], window: int) -> tuple[bool, float]:
    """Returns (is_cheap, hv_rank) for the most recent day, using the vetted
    window. is_cheap=True means the agent should buy optionality today."""
    rets = daily_returns(bars)
    hv = _hv_series(rets, window)
    if len(hv) < 2:
        raise ValueError("not enough bars for this window")
    history = hv[max(0, len(hv) - 1 - RANK_LOOKBACK_DAYS):-1]
    rank = _percentile_rank(hv[-1], history)
    return rank < CHEAP_VOL_PERCENTILE, rank


def direction_tiebreak(bars: Sequence[Bar], lookback: int = 10) -> int:
    """+1 (call) or -1 (put): once the vol regime says 'buy optionality',
    still need a side. Uses short-term trailing return direction as the
    tiebreaker — a modest edge, not the point of the strategy."""
    rets = daily_returns(bars)
    if len(rets) < lookback:
        raise ValueError("not enough bars for tiebreak lookback")
    return 1 if sum(rets[-lookback:]) > 0 else -1
