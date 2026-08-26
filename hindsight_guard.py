"""hindsight_guard — catch parameter choices that only look good because the
scoring window secretly included data that would not have been knowable yet
at decision time.

The failure shape: you sweep candidate parameters, score each one against
some window of data, and pick the best score. If that window spans past the
point that's supposed to be "unseen" (a holdout, a future period, anything
not available live), the number you optimized against is not the number
you'll actually get live — even though nothing about the code looks wrong.

This is a different failure from a stale *read* (the target of tools like
intervalguard for MCP tool-call caching): the data was never wrong or out of
date, it just extends further in time than the decision it's used to justify.

check_selection_leakage() re-runs your own scoring function twice — once on
the full window, once restricted to what was actually knowable in-sample —
and reports when they disagree about which candidate should win, or when
nothing clears the bar without the excluded data.

Origin: found by hand while auditing a trading strategy backtest where a
leverage cap was chosen using a score computed on the *total* period
(in-sample + out-of-sample + holdout combined). The in-sample score was
negative for every candidate; the "best" cap only won because the holdout
window was folded into the selection criterion. See demo_tsmom.py at
https://github.com/<user>/hindsight-guard for the real numbers.

This copy is vendored into hindsight-alpha (same author, MIT license) so the
agent has no path-dependent import to the sibling repo. Canonical source: the
author's separate hindsight-guard repository.

MIT license. Standard library only.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Sequence


class HindsightLeakError(Exception):
    """Raised when a selection only wins because of data outside the
    in-sample window, and raise_on_leak=True was requested."""


@dataclass
class LeakageReport:
    candidates: List[Any]
    full_scores: Dict[Any, float]
    in_sample_scores: Dict[Any, float]
    full_winner: Any
    in_sample_winner: Any
    in_sample_clears_bar: bool
    threshold: float
    unscorable: List[Any] = field(default_factory=list)
    agrees: bool = field(init=False)

    def __post_init__(self) -> None:
        # `unscorable` domine tout le reste: si un candidat n'a pas pu etre
        # note, on ne peut pas dire lequel gagne, donc on ne dit pas qu'il n'y
        # a pas de fuite.
        self.agrees = (
            not self.unscorable
            and self.full_winner == self.in_sample_winner
            and self.in_sample_clears_bar
        )

    def summary(self) -> str:
        lines = []
        if self.agrees:
            lines.append(
                f"OK: full-window winner ({self.full_winner!r}) matches the in-sample "
                f"winner and clears the threshold ({self.threshold})."
            )
        elif self.unscorable:
            lines.append(
                "CANNOT CONCLUDE: score_fn returned a non-finite value (NaN or "
                "infinity) for " + ", ".join(repr(c) for c in self.unscorable) + "."
            )
            lines.append(
                "  -> a candidate that could not be scored is not a candidate that "
                "lost. Refusing to certify this selection as leak-free."
            )
        else:
            lines.append("LEAK DETECTED: this selection depends on data outside the in-sample window.")
            lines.append(
                f"  full-window winner:      {self.full_winner!r}  "
                f"(score {self.full_scores[self.full_winner]:.4f})"
            )
            if self.in_sample_clears_bar:
                lines.append(
                    f"  in-sample winner:        {self.in_sample_winner!r}  "
                    f"(score {self.in_sample_scores[self.in_sample_winner]:.4f})"
                )
                lines.append("  -> the two windows disagree about which candidate is best.")
            else:
                best_is = max(self.in_sample_scores, key=self.in_sample_scores.get)
                lines.append(
                    f"  no candidate clears the in-sample threshold ({self.threshold}); "
                    f"best in-sample score is {self.in_sample_scores[best_is]:.4f} "
                    f"({best_is!r})."
                )
                lines.append(
                    "  -> the apparent winner exists only because the scoring window "
                    "included data that would not have been knowable at decision time."
                )
        return "\n".join(lines)


def check_selection_leakage(
    candidates: Sequence[Any],
    score_fn: Callable[[Any, str], float],
    *,
    threshold: float = 0.0,
    raise_on_leak: bool = False,
) -> LeakageReport:
    """Re-score every candidate on two windows and compare the winners.

    score_fn(candidate, window) -> float
        `window` is either "full" or "in_sample". This library never touches
        your data — score_fn decides what those two words mean (a date
        slice, a row mask, a different dataset entirely). All this function
        does is call it twice per candidate and compare verdicts.

    threshold
        A candidate only "clears the bar" in-sample if its in-sample score
        is strictly greater than this. Mirrors: an in-sample Sharpe that's
        negative doesn't justify picking anything, no matter how good the
        full-window number looks.

    raise_on_leak
        If True, raise HindsightLeakError instead of returning a report that
        says agrees=False. Useful as a hard gate in a pipeline; leave False
        to just inspect the report.
    """
    if not candidates:
        # `max()` sur un dictionnaire vide leve "max() arg is an empty
        # sequence", ce qui ne dit rien a l'appelant de ce qu'il a mal fait.
        raise ValueError(
            "check_selection_leakage() needs at least one candidate; got none. "
            "With a single candidate the disagreement test is vacuous by "
            "construction (the same candidate wins both windows), so two or "
            "more is what makes this check meaningful."
        )

    full_scores = {c: score_fn(c, "full") for c in candidates}
    in_sample_scores = {c: score_fn(c, "in_sample") for c in candidates}

    # AJOUTE le 26/08/2026. `max()` compare avec `>`, et toute comparaison avec
    # NaN rend False. Consequence mesuree, et elle depend de l'ORDRE:
    #
    #     scores {"A": nan, "B": 1.0}  -> gagnant A, agrees=False  (echoue ferme)
    #     scores {"A": 1.0, "B": nan}  -> gagnant A, agrees=TRUE   (le NaN est
    #                                     silencieusement ecarte, et le garde
    #                                     certifie l'absence de fuite)
    #
    # Un candidat qu'on n'a PAS PU noter n'est pas un candidat qui a perdu. Si
    # le vrai meilleur candidat echoue a se noter sur une fenetre -- donnee
    # manquante, division par zero -- il disparait sans bruit et un autre est
    # certifie propre. C'est un echec silencieux au coeur meme du mecanisme que
    # cette bibliotheque existe pour fournir.
    #
    # Non atteignable aujourd'hui par vol_strategy.py (`_sharpe` rend 0.0 sur
    # un ecart-type nul ou moins de deux points, et la porte qualite-donnees
    # refuse les barres aberrantes en amont). Mais cette bibliotheque est
    # explicitement concue pour un `score_fn` quelconque -- son propre
    # docstring dit qu'elle ne touche jamais aux donnees -- donc le cas est
    # ouvert pour tout autre appelant.
    unscorable = [
        c for c in candidates
        if not math.isfinite(full_scores[c]) or not math.isfinite(in_sample_scores[c])
    ]

    full_winner = max(full_scores, key=full_scores.get)
    in_sample_winner = max(in_sample_scores, key=in_sample_scores.get)
    in_sample_clears_bar = in_sample_scores[in_sample_winner] > threshold

    report = LeakageReport(
        candidates=list(candidates),
        full_scores=full_scores,
        in_sample_scores=in_sample_scores,
        full_winner=full_winner,
        in_sample_winner=in_sample_winner,
        in_sample_clears_bar=in_sample_clears_bar,
        threshold=threshold,
        unscorable=unscorable,
    )

    if raise_on_leak and not report.agrees:
        raise HindsightLeakError(report.summary())

    return report
