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

## What this week cannot prove

Five sessions. Four symbols. A handful of trades. Nothing here establishes
that the strategy has an edge, and no sentence written on 04/09 will change
that. What the week can establish is narrower and real: that the mechanism
runs unattended, refuses what it says it refuses, and reports its own
silences.
