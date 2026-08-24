"""Risk gates: one open position at a time, a per-trade capital cap, a
weekly drawdown lock, and take-profit/stop-loss position management.

Why this exists: an agent that can buy a new option every day with no check
on whether it already holds one, no cap on how much of the account it risks
per trade, and no circuit breaker if the week goes badly isn't a trading
agent — it's a liability generator that happens to have a good idea buried
inside it. The hackathon's required one-page write-up has to cover "risk
gates" explicitly; describing a policy in prose without enforcing it in code
would be exactly the kind of gap this whole project (hindsight_guard) exists
to catch in other people's work. This mirrors the discipline already
established and sealed in Spap's other trading project: a hard per-trade
risk cap and a drawdown lock, checked before every order, not just written
down.

State (starting equity, lock status) persists in state.json next to this
file so the weekly lock survives the agent being re-run as a scheduled job
across multiple days. Not a secret, but run-specific — see .gitignore.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import alpaca_cli

STATE_FILE = Path(__file__).parent / "state.json"

MAX_RISK_PCT_PER_TRADE = 0.01   # cap premium spent on any single trade at 1% of equity
WEEKLY_LOSS_LOCK_PCT = 0.03     # stop trading for the week if equity drops 3% from the start
MAX_OPEN_POSITIONS = 1          # never stack a second options position while one is open
TAKE_PROFIT_PCT = 0.50          # close a position once unrealized gain hits +50% of premium paid
STOP_LOSS_PCT = 0.50            # close a position once unrealized loss hits -50% of premium paid


@dataclass
class RiskDecision:
    allowed: bool
    reason: str
    qty: int = 0


def _load_state() -> dict:
    """Falls back to an empty state (not a crash) on a missing or corrupted
    state.json. This runs unattended for a week — a process killed mid-write
    (e.g. the machine sleeping during a scheduled run) is a real enough
    scenario that the whole agent shouldn't go down over it. Corruption
    means losing the recorded starting_equity and any lock, which is a
    real but bounded cost (re-baselines for the rest of the week) — safer
    than an agent that silently stops running every day because of one
    bad write."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:
        print(f"WARNING: {STATE_FILE} is corrupted — starting fresh (equity re-baselined, any lock cleared).")
        return {}


def _save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def _record_starting_equity(equity: float, state: dict, account_id: Optional[str]) -> dict:
    """Sets the baseline the weekly lock measures drawdown against — once,
    the first time this account is seen.

    account_id is compared against whatever is already saved in state.json.
    Without this check, switching .env from the dev account to the dedicated
    hackathon account at kickoff (a planned step, see PLAN_SPRINT.md) would
    silently compare the new account's real equity against the OLD account's
    starting_equity -- two unrelated numbers, since state.json is a single
    shared file with no account awareness. That could either falsely trip
    the weekly loss lock on the very first real run, or (worse) mis-size
    trades against a wrong baseline, depending on which account happened to
    have more equity. Re-baselining whenever the account_id changes makes
    the forgetting-to-wipe-state.json failure mode self-correcting instead
    of relying on remembering a manual step during the kickoff handoff."""
    if state.get("account_id") != account_id or "starting_equity" not in state:
        if state.get("account_id") not in (None, account_id):
            print(
                f"NOTE: state.json was for account {state.get('account_id')!r}, "
                f"now running as {account_id!r} -- re-baselining starting_equity and clearing any lock."
            )
        state["account_id"] = account_id
        state["starting_equity"] = equity
        state["locked"] = False
        state["lock_reason"] = None
        _save_state(state)
    return state


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


def manage_exits(dry_run: bool = False) -> List[str]:
    """Checks every open option position and closes any that have hit the
    take-profit or stop-loss threshold on unrealized P&L. Called once at
    the start of each run, before evaluating any new entry — position
    management isn't conditional on whether a new trade looks good today.
    Returns a human-readable action log line per position, for printing.

    dry_run=True never calls close_position (a real order), only reports
    what it would have done — same contract as agent.py's --dry-run for
    the rest of the pipeline."""
    actions: List[str] = []
    for pos in alpaca_cli.list_positions():
        asset_class = str(pos.get("asset_class", "")).lower()
        symbol = str(pos.get("symbol", ""))
        if "option" not in asset_class and not alpaca_cli._OCC_PATTERN.match(symbol):
            continue

        plpc = _extract_unrealized_plpc(pos)
        if plpc is None:
            actions.append(f"{symbol}: could not read unrealized P&L% — leaving position open")
            continue

        would_close_profit = plpc >= TAKE_PROFIT_PCT
        would_close_loss = plpc <= -STOP_LOSS_PCT

        if would_close_profit or would_close_loss:
            label = "take-profit" if would_close_profit else "stop-loss"
            if dry_run:
                actions.append(f"{symbol}: WOULD CLOSE — {label} hit ({plpc:+.1%})")
            else:
                alpaca_cli.close_position(symbol)
                actions.append(f"{symbol}: CLOSED — {label} hit ({plpc:+.1%})")
        else:
            actions.append(f"{symbol}: holding ({plpc:+.1%}, thresholds are +{TAKE_PROFIT_PCT:.0%}/-{STOP_LOSS_PCT:.0%})")
    return actions


def check_gates(option_symbol: str) -> RiskDecision:
    """Run every gate in order, cheapest/most-decisive first. Returns a
    single RiskDecision — allowed=False means agent.py must not trade,
    regardless of what the strategy/hindsight_guard verdict said."""
    account = alpaca_cli.get_account()
    equity = float(account.get("equity", account.get("portfolio_value", 0)))
    if equity <= 0:
        return RiskDecision(False, "could not read a usable equity figure from the account")

    account_id = account.get("id")
    state = _load_state()
    state = _record_starting_equity(equity, state, account_id)

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

    if MAX_OPEN_POSITIONS <= 0 or alpaca_cli.has_open_option_position():
        return RiskDecision(False, "already holding an open option position; not stacking a second one")

    ask = alpaca_cli.get_option_ask_price(option_symbol)
    if ask is None:
        return RiskDecision(False, f"could not price {option_symbol} (no usable ask found); refusing to trade blind")

    risk_dollars = equity * MAX_RISK_PCT_PER_TRADE
    cost_per_contract = ask * 100  # options are quoted per share, contracts are 100 shares
    qty = int(risk_dollars // cost_per_contract)
    if qty < 1:
        return RiskDecision(
            False,
            f"1 contract of {option_symbol} costs ~${cost_per_contract:,.2f}, "
            f"which exceeds the per-trade risk cap (${risk_dollars:,.2f} = "
            f"{MAX_RISK_PCT_PER_TRADE:.0%} of ${equity:,.2f} equity)",
        )

    return RiskDecision(True, f"cleared all gates: sizing {qty} contract(s) at ~${cost_per_contract:,.2f} each", qty)
