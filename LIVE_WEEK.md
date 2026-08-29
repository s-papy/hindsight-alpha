# The live week — what will be reported, decided before the results

**Written 28/08/2026, 22:15 CEST — after the agent's first live run, before
knowing what the week produces.** That timing is the point.

This repository rests on one idea: a parameter chosen after seeing the data
proves nothing. `hindsight_guard.check_selection_leakage` applies it to the
volatility window. This document applies it to the **report**.

On 04/09, with the numbers in hand, the natural thing would be to choose
which of them to show. That is not a suspicion about anyone — it is the
default behaviour of whoever writes a summary. The only protection is to
commit beforehand. So the list below is fixed now, and will not be
reordered later.

## What will be reported, in this order

**1. The refusal mechanism.** How many times the hindsight guard refused a
symbol, and which. The README already says it: *"The result worth judging is
not the P&L — it is that the refusal mechanism catches a real disagreement."*
This stays first whatever the P&L says.

**2. Execution regularity.** Scheduled runs versus actual runs. An agent that
did not run proved nothing, in either direction. A short list of refusals
because the agent was dead is not a result.

**3. Entries.** Orders submitted, and refusals by the risk gates.

**4. The P&L — last, and owned as such.** Over five sessions and a handful of
trades, this figure does not separate a strategy from a coin flip. It is
reported because it exists, not because it proves anything.

## What would count as a failure

Stated now, so it cannot be redefined afterwards:

- **The agent misses scheduled runs.** Then the week measured nothing, and
  that is the honest headline — not the trades that did happen.
- **The hindsight guard never fires all week.** The mechanism would be
  untested live. XLK was refused on day one, so this is already unlikely —
  but if the week had gone otherwise, saying so would have been the result.
- **A risk gate lets through what it exists to stop.** Any single occurrence
  is a failure, regardless of the P&L.

**A losing week is not on this list.** A refusal mechanism that works
perfectly on a strategy with no edge is still a refusal mechanism that works
— which is exactly, and only, what this repository claims to demonstrate.

## Where the numbers come from

    python3 bilan_semaine.py            # from the decision log alone
    python3 bilan_semaine.py --reseau   # plus the real equity at Alpaca

The script counts; it does not write prose. It reads `decision_log.jsonl`,
bounded by the window in `kickoff_freeze.json` — so runs from **before** the
kickoff, the ones used to develop the strategy, can never enter the count.
If that window cannot be read, the script stops instead of counting
everything: *"I don't know which entries count"* must never become *"I count
them all."*

Unreadable log lines are skipped **and counted in the output** — the count is
printed on every run, including when it is zero. A report that silently drops
part of its data is not a report.

*Added 29/08/2026, and it makes the rule stricter rather than looser: if
`decision_log.jsonl` cannot be opened **at all**, the script stops too. It used
to carry on and print "0 actual runs for 1 expected — 1 run MISSING", which
accuses the agent of something a failure to read a file caused. Nothing about
what will be reported has changed; this only says what happens when it cannot
be.*

## One record inside the window is not from the submitted account

*Disclosed 29/08/2026, after cross-checking the log against Alpaca's own
ledger. It cuts against this project, which is why it is written here rather
than left to be noticed.*

The hackathon requires a brand-new account. The one submitted — its number is
published on the dashboard, and only there — was created on 24/08 and funded
with exactly $100,000; its order history contains **one order**, submitted
28/08 at 19:37 UTC, the first live agent run. Nothing was traded on it before
the kickoff.

But the operator was still on a **different** paper account until that
evening, and `decision_log.jsonl` is a single append-only file that does not
record which account a run touched. One record therefore falls inside the live
window without belonging to the submitted account:

    2026-08-28T15:00:06Z   exit_monitor   SPY260903P00770000 closed, stop-loss −55%

That is **six seconds after the kickoff**, and the contract it names appears
nowhere in the submitted account's order history — which is how it can be
identified with certainty rather than by memory.

It is **not removed**: deleting a dated record because it is inconvenient is
the curation this repository argues against everywhere else. It also does not
enter the week's report — `bilan_semaine.py` counts agent runs, verdicts and
trades, and that record carries none of the three. It is visible on the public
dashboard, in date order, like everything else.

The reconciliation, run 29/08: Alpaca reports **1 order since the kickoff**;
the report says **`order_submitted 1`**. They agree, order for order.

## A prediction for Monday, written before Monday

*Added 29/08/2026 — a Saturday. The agent's next scheduled run is Monday
31/08 at 19:37 UTC. Writing this down now costs nothing if it is right and
costs credibility if it is wrong, which is the only reason it is worth
writing.*

Measured on Friday's closing bars, through the same code the agent runs:

| symbol | hindsight guard | volatility regime | expected |
|---|---|---|---|
| SPY | agrees (10d window) | HV rank **16.3** — cheap | the strategy wants it |
| GLD | agrees (90d) | HV rank 46.4 — not cheap | skip |
| XLK | **disagrees** (90 vs 10) | — | refused |
| XLV | agrees (10d) | HV rank 99.6 — not cheap | skip |

So the only symbol the strategy wants is SPY — and a SPY option position is
already open, which the risk gates refuse to stack on
(*"already holding an open option position on SPY; not stacking a second one
on the same underlying"*).

**Predicted outcome: zero new entries on Monday**, with SPY blocked by a risk
gate rather than by the market. That is the gates working, not a failure — but
it means one open 7-day option on the only tradeable symbol can block that
symbol for most of the judged week. Stated here so that a thin week of trades
is read as a consequence of the design, not as an agent that did nothing.

Monday's own bar will move all three HV ranks, so this is a projection, not a
certainty. GLD at 46.4 and XLV at 99.6 are far from cheap; SPY at 16.3 is well
inside. The one to watch is whether the open position exits first — it closes
at ±50 %, and it sat at −4.9 % on Friday.

## What this week cannot prove

Five sessions. Four symbols. A handful of trades. Nothing here establishes
that the strategy has an edge, and no sentence written on 04/09 will change
that. What the week can establish is narrower and real: that the mechanism
runs unattended, refuses what it says it refuses, and reports its own
silences.
