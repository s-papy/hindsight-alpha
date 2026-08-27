"""Time-series momentum (TSMOM) signal with a lookback-window sweep.

This is deliberately the same failure shape hindsight_guard was built to
catch: several candidate lookback windows are scored on daily bars, and the
naive approach picks whichever window has the best Sharpe ratio over the
*entire* fetched history. That's exactly the mistake documented in
hindsight-guard/demo_tsmom.py — the "winning" window can look great only
because its score secretly included the most recent (in-sample / decision-
time) days, days that in a live setting would not yet exist.

score_lookback() is the score_fn passed to hindsight_guard.check_selection_leakage.
"full" scores the window against the entire bar history fetched.
"in_sample" scores the window against everything except the most recent
IN_SAMPLE_HOLDOUT_DAYS bars — i.e., what would actually have been knowable
the day before today, before "today's" signal is used to trade.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import List, Sequence

IN_SAMPLE_HOLDOUT_DAYS = 20  # bars withheld from "in_sample" scoring
CANDIDATE_LOOKBACKS = [5, 10, 20, 40, 60]  # trading days


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


def _tsmom_returns(bars: Sequence[Bar], lookback: int) -> List[float]:
    """Strategy: go long if the asset is up over the trailing `lookback`
    days, short if down. Returns the resulting daily strategy returns
    (not buy-and-hold returns)."""
    rets = daily_returns(bars)
    strat_rets = []
    for i in range(lookback, len(rets)):
        signal = 1 if sum(rets[i - lookback:i]) > 0 else -1
        strat_rets.append(signal * rets[i])
    return strat_rets


def score_lookback(lookback: int, window: str, bars: Sequence[Bar]) -> float:
    """score_fn for hindsight_guard.check_selection_leakage.

    window="full"      -> Sharpe computed using every bar fetched.
    window="in_sample"  -> Sharpe computed using every bar except the most
                            recent IN_SAMPLE_HOLDOUT_DAYS — what would have
                            been knowable before "today".
    """
    if window == "full":
        usable_bars = bars
    elif window == "in_sample":
        cutoff = max(0, len(bars) - IN_SAMPLE_HOLDOUT_DAYS)
        usable_bars = bars[:cutoff]
    else:
        raise ValueError(f"unknown window: {window!r}")

    strat_rets = _tsmom_returns(usable_bars, lookback)
    return _sharpe(strat_rets)


def current_signal(bars: Sequence[Bar], lookback: int) -> int:
    """+1 (bullish) or -1 (bearish) using the most recent `lookback` days,
    for actually placing today's trade once a lookback has been vetted."""
    rets = daily_returns(bars)
    if len(rets) < lookback:
        raise ValueError("not enough bars for this lookback")
    return 1 if sum(rets[-lookback:]) > 0 else -1
