"""Historical-volatility-rank strategy: buy optionality (a call or a put)
when the underlying's realized volatility is cheap relative to its own
recent history, skip when it's already expensive.

Honesty note on what this is and isn't, corrected 24/08 after checking
Alpaca's docs directly rather than assuming: Alpaca does NOT expose a
historical time series of *implied* volatility (option IV) as a served
field — that's a derived quantity nobody hands you precomputed, you'd have
to reconstruct it yourself from historical option prices via a pricing
model. That specific claim still holds. What's corrected here: Alpaca DOES
offer historical option *price* data (bars/trades/quotes) via a dedicated
endpoint, since February 2024 -- an earlier version of this docstring
implied no historical option data existed at all, which overstated the
limitation. Two real caveats on that data, not reasons to ignore it: only
~2.5 years of history (Feb 2024 onward, vs. the multi-year stock history
this agent actually fetches), and the free-tier "Indicative" feed's quotes
are derivatives of the real OPRA feed with 15-minute-delayed trades, not
real consolidated BBO (that requires a paid OPRA subscription). Using that
option-price history to build a real premium-based backtest (actual entry/
exit prices, real bid-ask spread) instead of the proxy below is a legitimate
next step this project did not attempt -- out of scope for this build, not
overlooked from not knowing the data existed. Say it that way in the
write-up, not "the data doesn't exist."

Given that, this uses **realized/historical volatility rank (HV rank)**
computed purely from the underlying's daily closes, which is a standard
practical proxy: cheap realized vol tends to precede cheap option premiums,
and vice versa. Anyone reading this code or the pitch deck should see that
distinction, not a claim of using real option IV history.

The backtest payoff is also a deliberate simplification, not a Black-Scholes
options-pricing model: on any day where HV rank was low at entry, the proxy
reward is the next day's absolute return (the actual payoff shape of owning
optionality — you profit from the *size* of the move, not its direction)
minus a cost term proportional to the HV level at entry (options cost more
when volatility is already elevated; here it's ~always low when we'd enter,
but the term is kept so the score isn't free money by construction). This
keeps the whole sweep computable from stock bars only, which is simpler and
spans a much longer history than the ~2.5 years of option price data above
would allow — a real tradeoff, documented as one, not a claim that stock
bars were the only option available.

This mirrors momentum_strategy.py's pattern exactly (candidate windows,
full-vs-in-sample scoring for hindsight_guard) but is options-native: the
decision to trade is driven by a volatility regime, not just direction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import List, Sequence

IN_SAMPLE_HOLDOUT_DAYS = 20  # bars withheld from "in_sample" scoring
CANDIDATE_HV_WINDOWS = [10, 20, 30, 60, 90]  # trading days used to compute realized vol

# AJOUTE le 27/08/2026. `_realized_vol` ne peut rien mesurer sur moins de deux
# rendements ; `_hv_series` lui passe des tranches de EXACTEMENT `window`
# elements. Une fenetre < 2 rendrait donc une serie HV entierement non
# mesurable. Mesure avec window=1 :
#
#     _hv_series([...], 1) -> [0.0, 0.0, 0.0, 0.0]   « aucune volatilite, jamais »
#
# soit le rang le plus bas possible sur toute la serie : l'agent acheterait
# partout. Ce n'est pas atteignable aujourd'hui -- les fenetres candidates vont
# de 10 a 90 -- mais RIEN ne l'imposait, et la liste ci-dessus est le genre de
# constante qu'on modifie pour experimenter. On l'impose ici, a l'import.
if any(int(_w) < 2 for _w in CANDIDATE_HV_WINDOWS):
    raise ValueError(
        "CANDIDATE_HV_WINDOWS holds a window below 2 (%r): realized volatility "
        "needs at least two returns, so such a window yields no measurable "
        "volatility at all -- which reads as 'cheapest possible' and makes the "
        "agent buy everywhere." % (CANDIDATE_HV_WINDOWS,)
    )
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
    """Sharpe annualise, ou NaN quand il n'y a rien a mesurer.

    CORRIGE le 27/08/2026. Ces deux cas rendaient 0.0 -- un zero qui veut dire
    « je n'ai pas pu mesurer », strictement indiscernable d'un Sharpe mesure a
    zero. C'est une valeur FABRIQUEE, et elle remonte telle quelle dans
    hindsight_guard.check_selection_leakage() comme si c'etait un resultat.

    Reproduit le 27/08 : avec 325 barres au lieu des 592 que
    MIN_TRADING_DAYS_FOR_SWEEP exige, la fenetre 90 obtient ZERO echantillon,
    rend 0.000, et le garde conclut :

        OK: full-window winner (10) matches the in-sample winner and clears
        the threshold (0.0).

    `unscorable` etait vide : math.isfinite(0.0) est True, donc le garde
    NaN/infini ajoute le 26/08 ne voyait rien. Une fenetre qu'on n'a PAS PU
    noter etait comptee comme une fenetre qui a PERDU -- exactement la panne
    que ce garde existe pour empecher, au coeur meme du mecanisme.

    Le plus instructif : hindsight_guard.py justifiait sa propre portee en
    disant « non atteignable aujourd'hui par vol_strategy.py (_sharpe rend 0.0
    sur un ecart-type nul ou moins de deux points) », et un test verifiait
    cette propriete. La RAISON pour laquelle le cas n'etait pas atteignable
    ETAIT le defaut : la stratégie ne produisait jamais de non-fini parce
    qu'elle mentait a la place.

    NaN plutot qu'une exception : hindsight_guard sait deja traiter un score
    non-fini (il le range dans `unscorable` et refuse de certifier), et une
    exception ferait tomber tout le symbole la ou une seule fenetre est en
    cause. Rendre le mecanisme PORTANT plutot que defensif etait tout l'objet
    de ce garde.

    Balayage apres correctif, 400 series synthetiques x 5 longueurs tronquees
    (2000 combinaisons) : AUCUNE ne fait certifier une selection comportant une
    fenetre non notee. Avant correctif, la toute PREMIERE essayee en produisait
    une."""
    if len(returns) < 2:
        return float("nan")   # rien a mesurer, pas « mesure a zero »
    sd = pstdev(returns)
    if sd == 0:
        # Ecart-type nul : le ratio est 0/0, indefini. La strategie n'est
        # jamais entree sur cette fenetre -- ce n'est pas une performance
        # neutre, c'est une absence de mesure.
        return float("nan")
    return (mean(returns) / sd) * (252 ** 0.5)  # annualized, daily bars


def _realized_vol(returns: Sequence[float]) -> float:
    """Annualized realized volatility over the given return window, or NaN
    when there is nothing to measure.

    Rendait 0.0 jusqu'au 27/08/2026 -- meme faute que `_sharpe` avant sa
    correction : un « je n'ai pas pu mesurer » indiscernable d'un zero
    MESURE. Et zero est la volatilite la moins chere possible, donc le rang
    tombe a 0 et l'agent ACHETE. Un defaut qui autorise, pas qui refuse.

    NaN est sur ici parce que `_percentile_rank` refuse desormais de classer
    une valeur non finie au lieu de la lire comme « jamais aussi bon marche ».
    L'ordre des deux corrections compte : NaN seul aurait aggrave le defaut."""
    if len(returns) < 2:
        return float("nan")
    return pstdev(returns) * (252 ** 0.5)


def _hv_series(returns: Sequence[float], window: int) -> List[float]:
    """Rolling realized vol at each point in time (index i = vol computed
    from returns[i-window:i]). Length = len(returns) - window.

    🔒 ALIGNMENT INVARIANT -- verified numerically 24/08, on re-review, 
    and load-bearing. Do not "fix" the range below without re-checking both
    sides together.

    Two consequences of this indexing, neither obvious from the one-liner:

    1. hv[k]'s LAST observed return is returns[window+k-1], so the final
       return is never used by any element: hv[-1] is computed WITHOUT the
       most recent day's move. The volatility estimate is therefore one day
       stale, by construction.

    2. That staleness is IDENTICAL on both paths, which is what actually
       matters:
         - backtest (_vol_strategy_returns): decides on hv[i] (last info
           returns[window+i-1]) and takes its payoff from returns[window+i+1]
           -- one day skipped.
         - live (today_regime -> agent.py): decides on hv[-1] (last info
           returns[-2]) and buys now, capturing the NEXT move -- also one
           day skipped.
       Measured side by side on a synthetic series: gap of exactly 1 on
       both. So the backtest models the rule the agent actually trades,
       including its staleness -- it is not measuring a different, more
       favourable rule.

    This was checked because it is exactly the failure this whole project is
    named after, and an audit that took it on faith would be worthless. The
    first reading of it looked like a mismatch (backtest capturing a later
    day than live); working it through numerically showed both sides carry
    the same offset. Written down because a future edit that makes
    range(window, len(returns)+1) -- so hv[-1] finally uses the last return
    -- would silently break the correspondence on ONE side only, and the
    numbers would still look plausible."""
    return [_realized_vol(returns[i - window:i]) for i in range(window, len(returns))]


def _percentile_rank(value: float, history: Sequence[float]) -> float:
    # `not history` -> 50.0 : un historique VIDE ne permet pas de conclure, et
    # 50 est au-dessus de CHEAP_VOL_PERCENTILE, donc l'agent s'abstient. Ce
    # choix-la etait deja le bon ; on le laisse et on l'explicite.
    if not history:
        return 50.0

    # AJOUTE le 27/08/2026. Toute comparaison avec NaN est fausse, donc `below`
    # ne compte rien : le rang tombe a 0.0, c'est-a-dire « la volatilite n'a
    # jamais ete aussi bon marche » -- la reponse la PLUS agressive possible a
    # « je ne sais pas ». Mesure :
    #
    #     HV du jour = NaN             rang   0.0  -> ACHETE
    #     historique entierement NaN   rang   0.0  -> ACHETE
    #     1 NaN dans l'historique      rang  33.3  (temoin fini : 66.7)
    #     HV du jour = +inf            rang 100.0  -> s'abstient (cote sur)
    #
    # Meme un SEUL NaN dans l'historique fausse le rang vers le bas, donc vers
    # l'achat : les entrees non finies sont sous-comptees, jamais sur-comptees.
    # On refuse plutot que de les filtrer -- filtrer rendrait un rang calcule
    # sur une base silencieusement retrecie, ce qui est la meme faute en plus
    # discret.
    #
    # On leve : agent.py enveloppe chaque symbole dans un `except Exception`
    # qui en fait un refus NOMME. Renvoyer NaN ici ferait bien abstenir
    # (NaN < 30 est faux), mais sans dire pourquoi -- exactement le « 0.0 qui
    # veut dire je-n-ai-pas-pu-mesurer » que ce projet traque.
    if not math.isfinite(value):
        raise ValueError(
            "today's HV is %r, not a finite number -- every comparison with it "
            "is False, so the percentile rank would come out 0.0 and read as "
            "'volatility has never been cheaper'. Refusing to rank an "
            "unmeasurable value." % (value,)
        )
    non_finis = [h for h in history if not math.isfinite(h)]
    if non_finis:
        raise ValueError(
            "the ranking history holds %d non-finite value(s) out of %d "
            "(e.g. %r) -- they can only be UNDER-counted, which biases the "
            "rank down and the decision toward buying. Refusing to rank "
            "against a history that cannot be compared."
            % (len(non_finis), len(history), non_finis[0])
        )

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
