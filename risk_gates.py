"""Risk gates: several concurrent positions across different underlyings (not
stacked on the same one), a per-trade cap AND a total-exposure cap, a weekly
drawdown lock, and take-profit/stop-loss position management.

Why this exists: an agent that can buy a new option every day with no check
on whether it already holds one, no cap on how much of the account it risks
per trade, and no circuit breaker if the week goes badly isn't a trading
agent — it's a liability generator that happens to have a good idea buried
inside it. The hackathon's required one-page write-up has to cover "risk
gates" explicitly; describing a policy in prose without enforcing it in code
would be exactly the kind of gap this whole project (hindsight_guard) exists
to catch in other people's work. This mirrors the discipline already
established and sealed in an earlier trading project: a hard per-trade
risk cap and a drawdown lock, checked before every order, not just written
down.

Changed 24/08 from a strict single-position gate to several concurrent
positions, at the operator's explicit direction: "plusieurs symboles différents...
jamais tous les mêmes, œuf dans le même panier" (multiple different symbols,
never all the same, don't put all eggs in one basket) -- see agent.py's
DEFAULT_UNIVERSE, now spanning uncorrelated sectors (broad market,
commodities, tech, healthcare) instead of three similarly-correlated
broad-market ETFs. Allowing several open positions only makes sense with
symbols that are NOT highly correlated -- stacking positions on SPY, QQQ,
and IWM at the same time is close to one leveraged bet on the same regime,
not real diversification. This module doesn't check correlation itself
(no data source for that here); it trusts the universe was chosen with
that in mind.

Two caps now apply together, not just one: MAX_RISK_PCT_PER_TRADE bounds any
single trade, and MAX_TOTAL_RISK_PCT bounds the sum of premium committed
across every position open at once -- so opening a 4th position doesn't just
check "is there room for one more trade", it checks "is there still budget
left in the total exposure cap after what's already open". The weekly
drawdown lock did NOT need to change: it already compares total account
equity (which reflects every open position's unrealized P&L combined, not
per-position) against the recorded starting equity -- that check was already
portfolio-level by construction, verified by rereading it rather than
assumed correct just because it used to be.

Added 24/08, second pass, after a direct question "we improved the
strategy, but the agent is the real deliverable -- what improves the AGENT?"
and pointed at researching competitors and past hackathons for the answer.
Found in an Alpaca-published reference architecture (alpaca.markets/learn,
May 2026) and a separate trading-agent architecture guide (ampcome.com,
Aug 2026) -- both independently list "portfolio-level exposure caps that
[cannot be] individually breached" / max_sector_exposure_pct as a named
control, distinct from a per-position cap:

  MAX_SECTOR_EXPOSURE_PCT caps committed premium per SECTOR (SECTOR_MAP),
  not just per underlying. With today's 1-symbol-per-sector universe
  (agent.DEFAULT_UNIVERSE) this rarely binds in practice -- the existing
  duplicate-underlying block already prevents two positions on SPY at once,
  and SPY is the only "broad_market" symbol. But it stops being a no-op the
  moment the universe grows (e.g. adding QQQ alongside SPY, or a second
  tech ETF alongside XLK) -- exactly the "diversification is a policy, not
  a control" gap this module's docstring already warns against elsewhere.
  Coding it now, while it's cheap and low-risk to test, means the universe
  can grow later without silently reopening that gap.

State (starting equity, lock status) persists in state.json next to this
file so the weekly lock survives the agent being re-run as a scheduled job
across multiple days. Not a secret, but run-specific — see .gitignore.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import alpaca_cli

class StateNotPersisted(Exception):
    """Raised by the bookkeeping writers when _save_state() refused to write
    (corrupted state.json). Added 24/08 after a cleanup review: _save_state
    used to return None on refusal exactly as it did on success, so the
    caller-side guards written earlier the same day COULD NEVER FIRE on a
    corrupted file -- agent.py would log outcome="order_submitted" with no
    caveat while the duplicate-order guard was never armed, and manage_exits
    would state "consecutive losses now N" as fact with N not on disk. The
    choke point protected the evidence but dropped the signal that it had --
    the same family as the five bugs those guards were written for.

    Deliberately NOT caught by name anywhere -- checked 24/08 by reproducing
    both raise sites rather than by reading. The two generic handlers that
    already wrap these calls surface the message better than a named catch
    would:
      - agent.py puts it under its own key, record_order_submitted_failed,
        so decision_log.jsonl carries "StateNotPersisted: ... the
        duplicate-order guard was NOT armed for this order" as a dedicated
        field next to outcome="order_submitted", not buried in prose.
      - manage_exits appends it to the action line, which then reads
        "... CLOSED -- stop-loss hit (-60.0%) (consecutive-loss count NOT
        updated: StateNotPersisted: ...)" -- the close and the failed
        bookkeeping stated together, which is exactly what a human needs.
    A named except at either site would duplicate handling for no gain. The
    class earns its keep by making the message specific and greppable, not
    by being caught separately."""


STATE_FILE = Path(__file__).parent / "state.json"
HALT_FILE = Path(__file__).parent / "HALT"  # manual pause switch -- see is_halted()

MAX_RISK_PCT_PER_TRADE = 0.01   # cap premium spent on any single trade at 1% of equity
MAX_TOTAL_RISK_PCT = 0.03       # cap combined premium across ALL open positions at once at 3% of equity
MAX_SECTOR_EXPOSURE_PCT = 0.015 # cap combined premium within any ONE sector at 1.5% of equity (half the total cap)
WEEKLY_LOSS_LOCK_PCT = 0.03     # stop trading for the week if equity drops 3% from the start
MAX_OPEN_POSITIONS = 4          # never hold more than 4 positions at once, one per underlying
TAKE_PROFIT_PCT = 0.50          # close a position once unrealized gain hits +50% of premium paid
STOP_LOSS_PCT = 0.50            # close a position once unrealized loss hits -50% of premium paid
MAX_CONSECUTIVE_LOSSES = 3      # stop opening new positions after this many stop-losses in a row (see _record_exit_outcome)

# Maps each universe symbol to a sector bucket -- kept here (not in agent.py)
# since risk_gates is what enforces it. A symbol not in this map falls back
# to being its own sector (see sector_of) rather than silently landing in a
# shared "other" bucket, which would let two genuinely unrelated unmapped
# symbols quietly share a cap neither was designed against.
SECTOR_MAP = {
    "SPY": "broad_market",
    "GLD": "commodities",
    "XLK": "technology",
    "XLV": "healthcare",
}


def sector_of(symbol: str) -> str:
    return SECTOR_MAP.get(symbol.upper(), symbol.upper())


@dataclass
class RiskDecision:
    allowed: bool
    reason: str
    qty: int = 0
    committed_dollars: float = 0.0  # what this decision would add to total exposure, if allowed --
    # agent.py accumulates this, keyed by underlying, across a single run's
    # loop over several symbols (see check_gates'
    # already_committed_this_run_by_underlying param for why).


def _load_state() -> dict:
    """Falls back to an empty state (not a crash) on a MISSING state.json --
    that's just "first run," safe to start fresh. A CORRUPTED state.json
    (exists, but fails to parse) is handled very differently: returns a
    sentinel ({"_corrupted": True}) instead of quietly re-baselining, and
    check_gates() below refuses ALL new entries the moment it sees that
    sentinel, before ever touching starting_equity/locked.

    Correction made 24/08, on re-review, after re-reading this
    function's OWN reasoning and realizing it proved too much: the original
    version returned {} on corruption too, on the argument that "a process
    killed mid-write... is a real enough scenario that the whole agent
    shouldn't go down over it." True for a NEW/never-run state.json. Not
    true if the corruption hit a state.json that already had locked=True
    (the weekly drawdown lock) or a tripped consecutive_losses count --
    _record_starting_equity() treats "starting_equity missing from state"
    (which a corrupted file also produces) identically to "this account has
    never been seen before," and would have silently cleared BOTH the lock
    and the loss counter along with it. That's the exact opposite of fail-
    safe: a crash mid-write, at the worst possible moment, would have
    quietly un-paused an agent that was supposed to have stopped trading
    for the week. Corruption obscuring what the prior state actually was is
    a reason to be MORE cautious (refuse and wait for a human), not less --
    same principle already applied to the consecutive-loss breaker
    (deliberately not self-resetting). A human can always delete
    state.json by hand to intentionally re-baseline once they've confirmed
    it's safe; the agent should never do that silently on its own."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:
        print(
            f"WARNING: {STATE_FILE} exists but is corrupted (not valid JSON) -- likely a "
            "crash mid-write. This could be hiding an active weekly loss lock or "
            "consecutive-loss breaker from before the crash, so new entries are refused "
            "until a human looks (see check_gates). Exits are unaffected -- manage_exits() "
            "does not depend on this file being intact. Delete state.json by hand once "
            "you've confirmed it's safe to re-baseline from scratch."
        )
        return {"_corrupted": True}


def _save_state(state: dict) -> bool:
    """Refuses to write a state carrying the _corrupted sentinel -- found
    24/08, on re-review, by reproducing it rather than by inspection.

    _load_state() promises, in its own docstring, that a corrupted
    state.json is "left untouched on disk until a human deliberately
    intervenes". check_gates() honours that carefully (it refuses before
    ever calling _record_starting_equity). But the EXIT path does not go
    through check_gates at all -- by design, exits must keep running under
    a lock -- so manage_exits() -> _record_exit_outcome() reached
    _load_state() + _save_state() with no corruption check, and overwrote
    the damaged file with a freshly serialised one.

    Measured, on a real corrupted file that was hiding locked=true:
    starting_equity and locked were both GONE afterwards, replaced by
    {"_corrupted": true, "consecutive_losses": 1}.

    Scope of the damage, stated precisely: this did NOT open a trading
    hole. The _corrupted key survives the round-trip, so check_gates keeps
    refusing every new entry exactly as intended. What was destroyed is the
    EVIDENCE -- the bytes a human needs to decide whether a weekly lock was
    active before the crash -- while the module's own stated invariant said
    those bytes would be preserved.

    Guarding here rather than in each caller is deliberate: _save_state is
    the single choke point every writer already goes through, so this also
    covers record_order_submitted() (same latent shape, currently
    unreachable only because check_gates refuses first) and any writer
    added later, which a per-caller check would not."""
    if state.get("_corrupted"):
        print(
            f"  WARNING: refusing to overwrite {STATE_FILE} -- it is corrupted and its original "
            "contents are the only record of what was in effect before the crash (a weekly loss "
            "lock, a consecutive-loss count). Bookkeeping for this action was NOT persisted. "
            "New entries stay refused until a human deletes or repairs the file by hand."
        )
        return False

    # Atomic write -- found 24/08, on re-review, and demonstrated rather
    # than assumed: Path.write_text() opens in mode "w", which truncates the
    # file to 0 bytes BEFORE writing a single byte of the new content (probed
    # directly: 77 bytes -> 0 immediately on open, content only afterwards).
    # A process killed inside that window leaves a truncated or partial file
    # -- reproduced by killing a writer mid-write, which produced exactly the
    # invalid JSON _load_state() now flags as _corrupted.
    #
    # That mattered less this morning than it does now, for two reasons that
    # both landed today:
    #   - the corruption handling added earlier in this same pass makes a
    #     corrupted state.json STICKY on purpose: every new entry is refused
    #     until a human intervenes. Safe, but it means a torn write is no
    #     longer a transient annoyance -- it stops the agent for the rest of
    #     an unattended week.
    #   - monitor_exits.py is now scheduled every 15 minutes (launchd), so a
    #     SECOND process can reach this function at all, and the two can
    #     overlap. (Corrected 24/08 by a cleanup review: an earlier version
    #     of this note claimed the 15-minute cadence made writes happen "far
    #     more often". It does not -- manage_exits only reaches _save_state
    #     when a close actually fires, so the routine 15-minute path writes
    #     nothing. The overlap risk is real; the frequency claim was not.)
    #
    # Writing to a temp file in the same directory and os.replace()-ing it in
    # is atomic on POSIX: a reader (or a crash) sees either the complete old
    # file or the complete new one, never a half-written one. fsync before
    # the swap so the content is durable before it becomes visible.
    tmp = STATE_FILE.with_name(STATE_FILE.name + ".tmp")
    try:
        with open(tmp, "w") as fh:
            fh.write(json.dumps(state, indent=2))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, STATE_FILE)
    except Exception:
        # Leave no partial sidecar behind: a human doing the post-crash
        # forensics the _corrupted sentinel exists to force should find the
        # damaged state.json, not a second half-written file next to it.
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return True


def _record_starting_equity(equity: float, state: dict, account_id: Optional[str]) -> dict:
    """Sets the baseline the weekly lock measures drawdown against — once,
    the first time this account is seen.

    account_id is compared against whatever is already saved in state.json.
    Without this check, switching .env from the dev account to the dedicated
    hackathon account at kickoff (a planned step) would
    silently compare the new account's real equity against the OLD account's
    starting_equity -- two unrelated numbers, since state.json is a single
    shared file with no account awareness. That could either falsely trip
    the weekly loss lock on the very first real run, or (worse) mis-size
    trades against a wrong baseline, depending on which account happened to
    have more equity. Re-baselining whenever the account_id changes makes
    the forgetting-to-wipe-state.json failure mode self-correcting instead
    of relying on remembering a manual step during the kickoff handoff.

    Extended 24/08, second pass: also resets traded_today and
    consecutive_losses on an account switch. Both were added later the
    same day (duplicate-order guard, consecutive-loss circuit breaker) and
    were NOT included in the original reset list -- found by testing the
    exact kickoff scenario this function's own docstring describes (switch
    from dev to the dedicated account) against the two newer fields, not
    by inspection. Without this, a symbol already traded today on the OLD
    account would look "already traded" on a brand-new account that has
    never placed a single order, and a losing streak from the OLD account
    could immediately trip the circuit breaker on an account with zero
    real losses -- the identical failure shape this function already
    exists to prevent for starting_equity/locked, just not yet extended to
    fields added after it was written."""
    if state.get("account_id") != account_id or "starting_equity" not in state:
        if state.get("account_id") not in (None, account_id):
            print(
                f"NOTE: state.json was for account {state.get('account_id')!r}, "
                f"now running as {account_id!r} -- re-baselining starting_equity, clearing any lock, "
                f"today's traded-symbols record, and the consecutive-loss counter."
            )
        state["account_id"] = account_id
        state["starting_equity"] = equity
        state["locked"] = False
        state["lock_reason"] = None
        state["traded_today"] = {"date": _today(), "symbols": []}
        state["consecutive_losses"] = 0
        _save_state(state)
    return state


def _extract_float(position: dict, key: str) -> Optional[float]:
    """Same string-vs-number defensiveness as _extract_unrealized_plpc below,
    for any other numeric position field -- cost_basis in particular, needed
    to sum up total premium committed across multiple open positions."""
    value = position.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str) and value.strip():
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _total_committed(open_positions: List[dict]) -> float:
    """Sum of cost_basis across every open option position -- what's already
    at risk before sizing a new trade. Positions whose cost_basis can't be
    read are counted as 0, not skipped silently: printed so it's visible,
    but doesn't block sizing on data the CLI failed to provide cleanly."""
    total = 0.0
    for pos in open_positions:
        cost = _extract_float(pos, "cost_basis")
        if cost is None:
            print(f"  WARNING: could not read cost_basis for {pos.get('symbol')}, counting as $0 committed")
            continue
        total += cost
    return total


def _sector_committed(open_positions: List[dict], sector: str) -> float:
    """Sum of cost_basis across open positions whose underlying maps to the
    given sector -- the sector-level analogue of _total_committed above."""
    total = 0.0
    for pos in open_positions:
        underlying = alpaca_cli.option_underlying(pos)
        if underlying and sector_of(underlying) == sector:
            cost = _extract_float(pos, "cost_basis")
            if cost is not None:
                total += cost
    return total


def _extract_unrealized_plpc(position: dict) -> Optional[float]:
    """Unrealized P&L as a fraction of cost basis (0.5 = +50%). Tries
    Alpaca's standard field name first (unrealized_plpc, already a
    fraction), falls back to computing it from unrealized_pl / cost_basis
    if the CLI names it differently."""
    # VERIFIED 24/08 (`alpaca position list --schema`, CLI v0.0.13): every
    # numeric position field is typed *string* ("unrealized_plpc: string"),
    # so the original isinstance(plpc, (int, float)) check could never fire
    # against the real CLI. The result stayed correct only because the
    # fallback below recomputes from unrealized_pl / cost_basis -- but that
    # made the authoritative field dead code, and left the exit gate relying
    # on cost_basis being present and non-zero. Accept the string form.
    plpc = position.get("unrealized_plpc")
    if isinstance(plpc, (int, float)) and not isinstance(plpc, bool):
        return float(plpc)
    if isinstance(plpc, str) and plpc.strip():
        try:
            return float(plpc)
        except ValueError:
            pass
    pl = position.get("unrealized_pl")
    cost_basis = position.get("cost_basis")
    try:
        pl = float(pl)
        cost_basis = float(cost_basis)
    except (TypeError, ValueError):
        return None
    if cost_basis == 0:
        return None
    return pl / cost_basis


def _today() -> str:
    return datetime.utcnow().date().isoformat()


def already_traded_today(underlying: str) -> bool:
    """Local, process-independent duplicate-order guard -- checked FIRST in
    check_gates(), before anything that depends on the live API. Answers
    "did THIS process (or an earlier crashed one, today) already submit an
    order for this underlying", from state.json, not from re-querying
    Alpaca. That distinction matters: the already_committed_this_run_by_underlying/
    already_open_this_run_underlyings params added earlier today only protect
    against API lag WITHIN one run's loop over several symbols. They can't protect
    against agent.py crashing right after submit_paper_option_order()
    succeeds but before the position is visible via list_positions(), then
    being re-run (by the operator, or a cron retry) within that same lag window --
    a fresh process has no in-memory state, so it would re-evaluate the
    same symbol from scratch and could resubmit the identical order.
    Recording locally, synchronously, right after submission (see
    record_order_submitted) closes that gap independent of API timing.

    Added 24/08, second pass -- named "idempotency keys on every order...
    a retry after a timeout sends the order twice" in an external
    architecture guide researched after asking what would improve the
    AGENT, not the strategy."""
    state = _load_state()
    record = state.get("traded_today", {})
    return record.get("date") == _today() and underlying.upper() in record.get("symbols", [])


def record_order_submitted(underlying: str) -> None:
    """Call immediately after alpaca_cli.submit_paper_option_order()
    succeeds -- writes synchronously so the record survives even if the
    process crashes on the very next line. Resets the symbol list whenever
    the date rolls over, so this never accumulates across days."""
    state = _load_state()
    record = state.get("traded_today", {})
    if record.get("date") != _today():
        record = {"date": _today(), "symbols": []}
    if underlying.upper() not in record["symbols"]:
        record["symbols"].append(underlying.upper())
    state["traded_today"] = record
    if not _save_state(state):
        raise StateNotPersisted("state.json is corrupted; the duplicate-order guard was NOT armed for this order")


def is_halted() -> tuple:
    """Manual pause switch: create a file named HALT next to this module
    (any content, or empty) to stop the agent from opening any NEW
    position, without touching credentials, .env, or code -- checked
    before every entry attempt, in agent.py's _run(), AFTER manage_exits()
    has already run. Deliberately does not block exits: a halt is a
    risk-reducing pause on taking on MORE risk, not a reason to also stop
    closing positions that already hit take-profit/stop-loss -- the same
    asymmetry the weekly loss lock already has (see check_gates' lock,
    which also only blocks entries).

    Added 24/08, second pass, after asking what would improve the
    AGENT (not the strategy) and external research
    on both a Alpaca-published reference architecture and a separate
    trading-agent guide independently named an untested/inaccessible kill
    switch as a real production failure mode: "a kill switch nobody can
    activate at 2am is not a control." This is deliberately the simplest
    possible implementation of one -- a file, not a service, a database
    row, or a running process to keep alive -- because the whole point is
    that it has to work even if everything else about the agent's
    environment is degraded. Gitignored (see .gitignore): a local,
    ephemeral operational control, not something to publish or share the
    history of.

    Returns (halted: bool, reason: str)."""
    if not HALT_FILE.exists():
        return False, ""
    try:
        content = HALT_FILE.read_text().strip()
    except OSError:
        content = ""
    reason = content if content else "HALT file present (no reason given)"
    return True, reason


def _record_exit_outcome(is_win: bool, account_id: Optional[str] = None, equity: Optional[float] = None) -> int:
    """Updates the consecutive-loss counter in state.json: a win resets it
    to 0, a loss increments it. Returns the new count.

    Added 24/08, second pass -- "consecutive_losses: 3" appears as a named
    escalation trigger in an external trading-agent architecture guide,
    distinct from and complementary to the weekly %-drawdown lock: a fast
    losing streak can be a real signal before it adds up to -3% of equity.
    Scope, stated honestly: this only sees losses the AGENT ITSELF closed
    via manage_exits() (take-profit/stop-loss). A position closed some
    other way (manually by the operator, expiry, a broker-side liquidation) isn't
    seen here -- not full account-wide P&L tracking, just a check on the
    agent's own run of decisions, which is what MAX_CONSECUTIVE_LOSSES is
    actually meant to catch: "is my own signal currently not working."

    Once the counter reaches MAX_CONSECUTIVE_LOSSES, check_gates() blocks
    new entries -- a sticky stop, same as the weekly lock, cleared the same
    way (state.json reset or a win bringing the count back to 0 before the
    cap is hit). Deliberately NOT self-resetting once tripped: if new
    entries are blocked, no new trade can ever produce the win that would
    reset it, which is the point -- a losing streak is a "stop and have a
    human look" signal, not something the agent should quietly work
    through on its own.

    account_id/equity added 25/08, on re-review: this function used to
    mutate state["consecutive_losses"] with NO idea which account's exit
    actually caused the mutation. check_gates() is the only place that
    compares state.json's saved account_id against the currently active
    one and re-baselines (_record_starting_equity) -- and manage_exits()/
    monitor_exits.py never goes through check_gates() by design (exits
    must keep running under a lock, so they can't be gated on anything).
    Reproduced 25/08: seeded state.json as account "A"'s (consecutive_losses:
    1), then closed a losing position while alpaca_cli was mocked to
    represent a DIFFERENT account "B" -- consecutive_losses on disk went to
    2, still labeled account_id "A", with nothing anywhere recording that
    the loss producing that "2" was actually B's. Not hypothetical for this
    project specifically: monitor_exits.py is scheduled via launchd to run
    unattended every 15 minutes, and this same project's own workflow
    repeatedly swaps .env by hand for testing -- if that scheduled job ever
    fires during such a swap window, and .env is switched back before any
    check_gates() call happens on the account it was briefly pointed at,
    the real account's circuit breaker silently inherits a stranger's
    loss/win history, with no warning anywhere, because state.json's
    account_id never gets compared or corrected on this path.

    Fix: when account_id is supplied (manage_exits() always supplies it
    now), reconcile through the SAME _record_starting_equity() check_gates()
    already relies on -- a no-op when it already matches (every routine
    15-minute tick, once an account is settled), a full reset (including
    this very counter, to 0) when it doesn't, so the win/loss update below
    always applies to a freshly-correct baseline for whichever account's
    position actually just closed, never to a number left behind under
    someone else's account_id. Optional/default-None so a caller that
    genuinely doesn't have an account_id handy (none exist today, but
    future ones might in a mocked/offline context) degrades to the old,
    account-blind behavior rather than raising -- narrower than before, not
    a new failure mode."""
    state = _load_state()
    if account_id is not None:
        state = _record_starting_equity(equity or 0.0, state, account_id)
    count = 0 if is_win else state.get("consecutive_losses", 0) + 1
    state["consecutive_losses"] = count
    if not _save_state(state):
        raise StateNotPersisted(f"state.json is corrupted; the consecutive-loss count ({count}) was NOT persisted")
    return count


class ExitKind(str, Enum):
    """What happened to one position during a manage_exits() pass. A str
    Enum on purpose: `action.kind == "holding"` still reads naturally at
    every call site, no import of this class required just to compare."""
    HOLDING = "holding"
    CLOSED = "closed"
    WOULD_CLOSE = "would_close"
    UNREADABLE = "unreadable"  # position present, but its P&L% couldn't be read
    ERROR = "error"            # the close attempt itself raised


@dataclass
class ExitAction:
    """Structured replacement (24/08) for the plain human-readable strings
    manage_exits() used to return. Found while writing the persistent-
    failure dedup logic in monitor_exits.py: deciding "is this the same
    problem as last time" by re-parsing a sentence built for a human to
    read (matching ": holding (" as the one routine substring) was already
    fragile -- the exact gap the engineering log flagged as "the last place in
    the code where a human-readable string decides control flow" once the
    other four were fixed earlier. `kind` and the structured fields below
    are what callers should branch on; `text` / `__str__` exist purely for
    display and are kept byte-for-byte identical to the original sentences
    so `monitor_exits.log` and printed output don't change shape.

    `to_dict()` is what actually lands in decision_log.jsonl and therefore
    docs/data.json -- a plain, JSON-serializable dict, never this class
    itself. docs/index.html was updated alongside this to accept either
    shape, since decision_log.jsonl is committed (never rewritten) and
    already holds thousands of exit_actions entries as bare strings from
    before this change."""
    symbol: str
    kind: ExitKind
    pnl_pct: Optional[float] = None
    label: Optional[str] = None  # "take-profit" / "stop-loss", set for CLOSED/WOULD_CLOSE
    consecutive_losses: Optional[int] = None  # set only on a successful stop-loss CLOSE
    bookkeeping_error: Optional[str] = None   # set only if that same streak update then failed
    error: Optional[str] = None               # exception text, for UNREADABLE / ERROR

    def __str__(self) -> str:
        if self.kind == ExitKind.HOLDING:
            return (f"{self.symbol}: holding ({self.pnl_pct:+.1%}, thresholds are "
                     f"+{TAKE_PROFIT_PCT:.0%}/-{STOP_LOSS_PCT:.0%})")
        if self.kind == ExitKind.UNREADABLE:
            return f"{self.symbol}: could not read unrealized P&L% — leaving position open"
        if self.kind == ExitKind.WOULD_CLOSE:
            return f"{self.symbol}: WOULD CLOSE — {self.label} hit ({self.pnl_pct:+.1%})"
        if self.kind == ExitKind.CLOSED:
            if self.consecutive_losses is not None:
                streak_note = f", consecutive losses now {self.consecutive_losses}"
            elif self.bookkeeping_error is not None:
                streak_note = f" (consecutive-loss count NOT updated: {self.bookkeeping_error})"
            else:
                streak_note = ""
            return f"{self.symbol}: CLOSED — {self.label} hit ({self.pnl_pct:+.1%}){streak_note}"
        if self.kind == ExitKind.ERROR:
            return f"{self.symbol}: ERROR managing this position ({self.error}) — left open, check manually"
        return f"{self.symbol}: {self.kind.value}"  # unreachable in practice; never silently blank

    def to_dict(self) -> dict:
        d: dict = {"symbol": self.symbol, "kind": self.kind.value, "text": str(self)}
        if self.pnl_pct is not None:
            d["pnl_pct"] = round(self.pnl_pct, 4)
        if self.label is not None:
            d["label"] = self.label
        if self.consecutive_losses is not None:
            d["consecutive_losses"] = self.consecutive_losses
        if self.bookkeeping_error is not None:
            d["bookkeeping_error"] = self.bookkeeping_error
        if self.error is not None:
            d["error"] = self.error
        return d

    def is_routine(self) -> bool:
        return self.kind == ExitKind.HOLDING

    def failure_signature(self) -> Optional[tuple]:
        """Identity used by monitor_exits.py to recognize "this is the same
        stuck problem as last time" rather than a fresh one. None for
        anything that isn't a failure (holding/closed/would_close never
        need dedup: holding is filtered before logging anyway, and a close
        can't repeat -- the position leaves list_positions() once it's
        closed).

        Uses only the leading "ExceptionType" prefix of `error`, not the
        full text -- found minutes after writing the first version, by
        reproducing against a realistic error message instead of trusting
        the mocked static strings every test up to that point had used.
        alpaca_cli.py builds AlpacaCLIError from `result.stderr` (see its
        _run_cli, subprocess error path), which for a real transient network
        failure varies call to call (connection timing, a retry count the
        CLI itself reports) even when it's the exact same underlying
        problem recurring. Keying on the full string meant the SAME stuck
        failure produced a DIFFERENT signature almost every 15-minute check
        -- monitor_exits.py's heartbeat throttle would never engage against
        the one case (a persistent network/API issue) it exists to catch,
        silently reverting to logging every occurrence, the exact flooding
        this dedup layer was built to prevent. `type(e).__name__: message`
        is the format every raise site in this codebase already follows
        (grepped, not assumed), so splitting on the first ": " reliably
        recovers a stable exception-class identity; a message with no colon
        (e.g. UNREADABLE's fixed string, which has none) falls back to the
        whole string unchanged, so that case is unaffected."""
        if self.kind in (ExitKind.ERROR, ExitKind.UNREADABLE):
            error_kind = (self.error or "").split(":", 1)[0].strip() or (self.error or "")
            return (self.symbol, self.kind.value, error_kind)
        return None


def manage_exits(dry_run: bool = False) -> List[ExitAction]:
    """Checks every open option position and closes any that have hit the
    take-profit or stop-loss threshold on unrealized P&L. Called once at
    the start of each run, before evaluating any new entry — position
    management isn't conditional on whether a new trade looks good today.
    Returns one structured ExitAction per position (see that class) --
    `str(action)` reproduces the original human-readable line, for
    printing and for anything reading old decision_log.jsonl entries.

    dry_run=True never calls close_position (a real order), only reports
    what it would have done — same contract as agent.py's --dry-run for
    the rest of the pipeline. Consistently, it also does NOT update the
    consecutive-loss counter in dry-run mode -- a simulated close is not a
    real outcome to count.

    Each position's close attempt is wrapped in its own try/except -- found
    24/08, on re-review, the most important gap of the day: this loop
    can hold up to MAX_OPEN_POSITIONS positions since the multi-position
    redesign, but close_position() was called with NO per-position
    isolation, unlike every other per-item loop already fixed earlier today
    (evaluate_symbol, agent.py's entry loop, backtest.py,
    compare_strategies.py). If closing position A raised (a transient CLI
    hiccup, a network blip, an already-closed position via a race with a
    manual close) the exception would propagate straight out of this
    function -- meaning position B, checked immediately after A in the same
    loop, would NEVER get its own take-profit/stop-loss check THIS run, even
    if B independently needed closing too. This is the single function
    monitor_exits.py exists to make sure keeps running often -- and unlike
    every other exception-isolation gap found today (which all failed safe,
    just refusing otherwise-fine trades), this one is the first to fail on
    the DANGEROUS side: a real losing position could sit open, unmanaged,
    specifically because an unrelated position's close attempt failed
    earlier in the same loop. Not yet triggered for real -- found by
    re-reading this function immediately after fixing the same-shaped gap
    in check_gates(), not by a live failure."""
    actions: List[ExitAction] = []
    for pos in alpaca_cli.list_positions():
        asset_class = str(pos.get("asset_class", "")).lower()
        symbol = str(pos.get("symbol", ""))
        if "option" not in asset_class and not alpaca_cli._OCC_PATTERN.match(symbol):
            continue

        try:
            plpc = _extract_unrealized_plpc(pos)
            if plpc is None:
                actions.append(ExitAction(symbol, ExitKind.UNREADABLE,
                                           error="unrealized_plpc missing or unparseable in `alpaca position list` output"))
                continue

            would_close_profit = plpc >= TAKE_PROFIT_PCT
            would_close_loss = plpc <= -STOP_LOSS_PCT

            if would_close_profit or would_close_loss:
                label = "take-profit" if would_close_profit else "stop-loss"
                if dry_run:
                    actions.append(ExitAction(symbol, ExitKind.WOULD_CLOSE, pnl_pct=plpc, label=label))
                else:
                    alpaca_cli.close_position(symbol)
                    # _record_exit_outcome() is bookkeeping AFTER the close
                    # already succeeded -- wrapped in its own inner
                    # try/except, separate from the outer one, so that a
                    # failure updating the consecutive-loss counter (a
                    # state.json write hiccup, for instance) can never get
                    # mislabeled by the outer except as "left open, check
                    # manually" below. Found 24/08 re-reading my OWN fix
                    # from moments earlier in this same review pass
                    # pass: the position IS closed at this point -- only the
                    # streak count might be stale -- and reporting the
                    # opposite would be actively misleading, not just
                    # unhelpful, on the one action (a real stop-loss firing)
                    # this project cares most about being honest about.
                    consecutive_losses = None
                    bookkeeping_error = None
                    # account/equity fetched here, not once at the top of
                    # manage_exits() -- only paid for when a close actually
                    # fires (rare: most 15-minute ticks are all HOLDING),
                    # same "only pay the API cost when you actually need to
                    # act" shape as _check_cli_version's once-per-process
                    # cache. See _record_exit_outcome's docstring for why
                    # this call exists at all: without it, this bookkeeping
                    # had no way to notice state.json belongs to a
                    # DIFFERENT account than the one that just closed.
                    account_id = None
                    account_equity = None
                    try:
                        account = alpaca_cli.get_account()
                        account_id = account.get("id")
                        account_equity = float(account.get("equity", account.get("portfolio_value", 0)))
                    except Exception as e:
                        # Can't reconcile the account without this call --
                        # fall through with account_id=None, which makes
                        # _record_exit_outcome skip reconciliation entirely
                        # (old, account-blind behavior) rather than guessing.
                        print(f"  WARNING: could not fetch account info to reconcile {symbol}'s exit "
                              f"bookkeeping against the correct account ({type(e).__name__}: {e}) -- "
                              "recording the outcome against state.json's existing account_id as-is.")
                    if not would_close_profit:
                        try:
                            consecutive_losses = _record_exit_outcome(is_win=False, account_id=account_id, equity=account_equity)
                        except Exception as e:
                            bookkeeping_error = f"{type(e).__name__}: {e}"
                    else:
                        try:
                            _record_exit_outcome(is_win=True, account_id=account_id, equity=account_equity)
                        except Exception as e:
                            print(f"  WARNING: {symbol} closed on a win but failed to reset the "
                                  f"consecutive-loss counter ({type(e).__name__}: {e}) -- the close "
                                  "itself is unaffected.")
                    actions.append(ExitAction(symbol, ExitKind.CLOSED, pnl_pct=plpc, label=label,
                                               consecutive_losses=consecutive_losses,
                                               bookkeeping_error=bookkeeping_error))
            else:
                actions.append(ExitAction(symbol, ExitKind.HOLDING, pnl_pct=plpc))
        except Exception as e:
            actions.append(ExitAction(symbol, ExitKind.ERROR, error=f"{type(e).__name__}: {e}"))
    return actions


def check_gates(
    underlying: str,
    option_symbol: str,
    already_committed_this_run_by_underlying: Optional[Dict[str, float]] = None,
    already_open_this_run_underlyings: Optional[set] = None,
) -> RiskDecision:
    """Run every gate in order, cheapest/most-decisive first. Returns a
    single RiskDecision — allowed=False means agent.py must not trade,
    regardless of what the strategy/hindsight_guard verdict said.

    underlying is the stock symbol this option is written on (e.g. "SPY"),
    separate from option_symbol (the OCC contract, e.g. "SPY260831P00763000")
    -- needed since 24/08 to check "is a position already open on THIS
    underlying" without re-parsing the OCC string, now that several
    concurrent positions on DIFFERENT underlyings are allowed.

    already_committed_this_run_by_underlying / already_open_this_run_underlyings,
    added 24/08 after noticing the gap: agent.py can now attempt several
    symbols in ONE run, calling check_gates() once per symbol in a loop.
    Each call re-reads alpaca_cli.list_open_option_positions() from the live
    API -- but a just-submitted paper order isn't guaranteed to show up in
    that list immediately (order submit returns on acceptance, not
    necessarily on fill). Without these params, a second or third symbol in
    the SAME run could pass the total-exposure, sector, and position-count
    checks as if the earlier order(s) from THIS SAME run never happened,
    silently exceeding MAX_TOTAL_RISK_PCT / MAX_SECTOR_EXPOSURE_PCT /
    MAX_OPEN_POSITIONS in aggregate before the API catches up. agent.py
    accumulates both, keyed by underlying, across its loop and passes them
    in on every call after the first.

    Keyed by underlying (not a running total/count) since 24/08, second
    fix, a review pass: the original version of this same-run-lag fix
    (added earlier the same day) took a single running float/int and always
    added it in full, on the assumption the live API is ALWAYS behind
    within one run. That's not guaranteed -- a paper order can fill and
    become visible in list_open_option_positions() before the next symbol
    in agent.py's loop gets checked, especially with only 2-3 API calls
    between submissions. If that happens, the same position would be
    counted TWICE: once via open_positions (now that the API caught up) and
    once via the unconditional this-run addition -- silently shrinking the
    real remaining budget more than actually true. Direction is fail-safe
    (more conservative, not less -- refuses trades that were actually still
    safe, never allows an unsafe one), but a P&L-judged week doesn't want
    real trades refused for a phantom reason either. Fixed by tracking
    per-underlying dollars/membership and only counting an underlying's
    this-run contribution if it does NOT already show up in
    already_on_this_underlying below -- if the API has caught up, the
    freshly-fetched open_positions already accounts for it, so adding the
    this-run figure too would double it.

    Duplicate-underlying isn't at the same risk either way: the loop only
    ever visits each universe symbol once per run, so it can't attempt the
    same underlying twice in a single run by construction."""
    account = alpaca_cli.get_account()
    equity = float(account.get("equity", account.get("portfolio_value", 0)))
    if equity <= 0:
        return RiskDecision(False, "could not read a usable equity figure from the account")

    account_id = account.get("id")
    state = _load_state()

    # Checked BEFORE _record_starting_equity(): a corrupted state.json (see
    # _load_state's docstring) would otherwise be treated identically to a
    # brand-new account and silently re-baselined -- clearing any weekly
    # loss lock or consecutive-loss count that was in effect before the
    # corruption happened. Refusing here, without ever calling
    # _record_starting_equity, means state.json is left untouched on disk
    # (still corrupted) until a human deliberately intervenes, rather than
    # this function silently "fixing" it by overwriting it with a fresh,
    # unlocked state.
    if state.get("_corrupted"):
        return RiskDecision(
            False,
            f"{STATE_FILE} is corrupted and could not be parsed -- refusing all new "
            "entries until a human looks (it may be hiding an active weekly loss lock "
            "or consecutive-loss breaker from before a crash). Delete state.json by hand "
            "once you've confirmed it's safe to re-baseline. Exits are unaffected.",
        )

    state = _record_starting_equity(equity, state, account_id)

    # already_traded_today() reads state["traded_today"], which
    # _record_starting_equity() above has just reset if the account
    # changed -- MUST run after that reset, not before. Originally placed
    # before the account fetch (to skip an API call in the common case),
    # moved here 24/08 after finding the bug: a stale traded_today (or
    # consecutive_losses) record from an OLD account would otherwise leak
    # into a brand-new account with zero real trades on it -- the same
    # failure shape _record_starting_equity was already written to prevent
    # for starting_equity/locked, just not extended to these two newer
    # fields when they were added. See the engineering log for the caught-and-
    # fixed writeup; found by testing this exact scenario, not by
    # inspection.
    if already_traded_today(underlying):
        return RiskDecision(False, f"already submitted an order for {underlying} today (local record, state.json) -- not resubmitting on a rerun")

    if state.get("locked"):
        return RiskDecision(False, f"weekly loss lock already active: {state.get('lock_reason')}")

    starting_equity = state["starting_equity"]
    drawdown_pct = (starting_equity - equity) / starting_equity if starting_equity else 0
    if drawdown_pct >= WEEKLY_LOSS_LOCK_PCT:
        reason = (
            f"equity down {drawdown_pct:.1%} from the recorded starting equity "
            f"(${starting_equity:,.2f} -> ${equity:,.2f}), >= the {WEEKLY_LOSS_LOCK_PCT:.0%} weekly lock threshold"
        )
        state["locked"] = True
        state["lock_reason"] = reason
        _save_state(state)
        return RiskDecision(False, f"weekly loss lock triggered: {reason}")

    consecutive_losses = state.get("consecutive_losses", 0)
    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        return RiskDecision(
            False,
            f"consecutive-loss circuit breaker: {consecutive_losses} stop-losses in a row "
            f"(>= {MAX_CONSECUTIVE_LOSSES}) -- pausing new entries for a human to look, not resetting on its own",
        )

    open_positions = alpaca_cli.list_open_option_positions()

    already_on_this_underlying = {
        alpaca_cli.option_underlying(pos) for pos in open_positions
    }
    if underlying.upper() in already_on_this_underlying:
        return RiskDecision(False, f"already holding an open option position on {underlying}; not stacking a second one on the same underlying")

    # CORRIGE le 26/08/2026. Ce controle ne consultait QUE l'API, alors que
    # `already_open_this_run_underlyings` existe precisement pour couvrir la
    # fenetre ou l'API n'a pas encore rattrape. Ce parametre n'alimentait que
    # le compteur de positions simultanees, plus bas -- pas la regle
    # anti-doublon, dont il porte pourtant le nom.
    #
    # TROU REPRODUIT, et il demande DEUX conditions:
    #   1. le meme sous-jacent deux fois dans une execution. `agent.py` fait
    #      `[s.strip().upper() for s in args.symbols.split(",")]` SANS
    #      dedoublonner, donc `--symbols SPY,SPY` suffit.
    #   2. l'echec de `record_order_submitted()` -- cas qu'agent.py prevoit
    #      explicitement, signale par un AVERTISSEMENT, et apres lequel il
    #      continue. Sans cet enregistrement, le garde `traded_today` de
    #      state.json ne rattrape plus rien.
    # Mesure: deux ordres sur SPY dans la meme execution, contre une regle
    # que ce projet enonce comme non negociable.
    #
    # A noter, et c'est rassurant sur le reste: l'accumulateur d'exposition
    # TOTALE fonctionnait pendant ce trou -- le second passage dimensionnait 2
    # contrats au lieu de 3, il savait donc que 840 $ etaient deja engages.
    # Seule la regle anti-doublon cedait.
    run_open_upper = {u.upper() for u in (already_open_this_run_underlyings or set())}
    if underlying.upper() in run_open_upper:
        return RiskDecision(
            False,
            f"already submitted an order for {underlying} earlier in THIS run; not stacking a "
            "second one on the same underlying (the live API may not show it yet)",
        )

    # Only count a this-run underlying's contribution if the live API does
    # NOT already show it as open -- otherwise it's already counted via
    # open_positions below, and adding it again would double it. See this
    # function's docstring for the exact failure this prevents.
    run_committed = already_committed_this_run_by_underlying or {}
    run_committed_not_yet_visible = {
        u: v for u, v in run_committed.items() if u.upper() not in already_on_this_underlying
    }
    run_open_underlyings = already_open_this_run_underlyings or set()
    run_open_not_yet_visible = [u for u in run_open_underlyings if u.upper() not in already_on_this_underlying]

    sector = sector_of(underlying)
    sector_committed_this_run = sum(v for u, v in run_committed_not_yet_visible.items() if sector_of(u) == sector)
    sector_committed = _sector_committed(open_positions, sector) + sector_committed_this_run
    sector_cap_dollars = equity * MAX_SECTOR_EXPOSURE_PCT
    remaining_sector_budget = sector_cap_dollars - sector_committed
    if remaining_sector_budget <= 0:
        return RiskDecision(
            False,
            f"sector concentration cap reached for {sector!r}: ${sector_committed:,.2f} already committed, "
            f">= the {MAX_SECTOR_EXPOSURE_PCT:.1%} sector cap (${sector_cap_dollars:,.2f} of ${equity:,.2f} equity)",
        )

    effective_open_count = len(open_positions) + len(run_open_not_yet_visible)
    if MAX_OPEN_POSITIONS <= 0 or effective_open_count >= MAX_OPEN_POSITIONS:
        return RiskDecision(
            False,
            f"already at the concurrent-position cap ({effective_open_count}/{MAX_OPEN_POSITIONS} open"
            + (f", including {len(run_open_not_yet_visible)} opened earlier this run" if run_open_not_yet_visible else "")
            + ")",
        )

    ask = alpaca_cli.get_option_ask_price(option_symbol)
    if ask is None:
        return RiskDecision(False, f"could not price {option_symbol} (no usable ask found); refusing to trade blind")

    cost_per_contract = ask * 100  # options are quoted per share, contracts are 100 shares

    committed_this_run = sum(run_committed_not_yet_visible.values())
    committed = _total_committed(open_positions) + committed_this_run
    total_cap_dollars = equity * MAX_TOTAL_RISK_PCT
    remaining_total_budget = total_cap_dollars - committed
    if remaining_total_budget <= 0:
        return RiskDecision(
            False,
            f"total exposure cap reached: ${committed:,.2f} already committed across "
            f"{effective_open_count} position(s)"
            + (f" (${committed_this_run:,.2f} of that from earlier this run)" if committed_this_run else "")
            + f", >= the {MAX_TOTAL_RISK_PCT:.0%} total cap (${total_cap_dollars:,.2f} of ${equity:,.2f} equity)",
        )

    per_trade_dollars = min(equity * MAX_RISK_PCT_PER_TRADE, remaining_total_budget, remaining_sector_budget)
    qty = int(per_trade_dollars // cost_per_contract)
    if qty < 1:
        return RiskDecision(
            False,
            f"1 contract of {option_symbol} costs ~${cost_per_contract:,.2f}, "
            f"which exceeds the available budget for this trade (${per_trade_dollars:,.2f} "
            f"= min of the {MAX_RISK_PCT_PER_TRADE:.0%} per-trade cap, the "
            f"${remaining_total_budget:,.2f} left under the {MAX_TOTAL_RISK_PCT:.0%} total cap, and the "
            f"${remaining_sector_budget:,.2f} left under the {MAX_SECTOR_EXPOSURE_PCT:.1%} {sector!r} sector cap)",
        )

    actual_cost = qty * cost_per_contract
    return RiskDecision(
        True,
        f"cleared all gates: sizing {qty} contract(s) at ~${cost_per_contract:,.2f} each",
        qty,
        committed_dollars=actual_cost,
    )
