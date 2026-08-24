"""Thin subprocess wrapper around Alpaca's official CLI (github.com/alpacahq/cli).

Using the CLI here — instead of the alpaca-py SDK, which the first draft of
this agent used — is a deliberate choice, not an implementation detail:

1. The hackathon's core requirement is explicit: "MCP or CLI — projects must
   utilize either Alpaca's MCP server or its CLI tools." Calling the Trading
   API directly through a Python SDK doesn't satisfy that.
2. Alpaca's own CLI docs recommend the CLI over the MCP server specifically
   for this shape of agent: "CLI: Scripts, cron, CI, focused agent actions.
   MCP Server: Long-lived AI sessions, multi-tool orchestration." This agent
   runs as one command per invocation (a scheduled sweep + trade-or-refuse
   decision), then exits — exactly the CLI's designed use case, not the
   MCP server's (which expects a persistent session with an AI host
   attached, e.g. Claude Desktop or Cursor, driving it interactively).

Requires the `alpaca` binary on PATH:
    brew install alpacahq/tap/cli          (macOS/Linux)
    go install github.com/alpacahq/cli/cmd/alpaca@latest

Authenticates via ALPACA_API_KEY / ALPACA_SECRET_KEY env vars (see
config.py). Paper trading is the CLI's default; config.cli_env() explicitly
strips ALPACA_LIVE_TRADE so nothing in this process can accidentally opt
into live trading.

Note on JSON shapes below: the CLI wraps Alpaca's REST API and is documented
to return "structured JSON" but the exact field names for a couple of
commands (`data bars`, options contracts via raw API) weren't shown with a
sample payload in the docs available while writing this offline. Parsing
here defensively tries the REST API's known shapes (short keys like "c" for
close, "bars" nested by symbol) — flagged explicitly in BRIEF_TEST_AGENT_TERMINAL.md
as the first thing to verify once this runs against the real CLI, with
`--schema` (a real CLI flag) as the way to check without spending a call.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime, timedelta
from typing import Any, List, Optional

import config
from vol_strategy import MIN_TRADING_DAYS_FOR_SWEEP, Bar


class AlpacaCLIError(Exception):
    """Raised when the `alpaca` CLI exits non-zero or returns unparseable output."""


def _require_binary() -> None:
    if shutil.which("alpaca") is None:
        raise AlpacaCLIError(
            "The `alpaca` CLI is not on PATH. Install it with "
            "`brew install alpacahq/tap/cli` (macOS) or "
            "`go install github.com/alpacahq/cli/cmd/alpaca@latest`, then retry.\n"
            "Run `alpaca doctor` after installing to verify."
        )


def run(args: List[str]) -> Any:
    """Run `alpaca <args>` and return the parsed JSON stdout.

    Always appends --quiet (a real, documented CLI flag: "suppress non-
    essential output"). Without it, a banner, update notice, or any other
    human-readable text the CLI prints ahead of the JSON payload would break
    json.loads on the combined stdout — a real risk for a CLI explicitly
    labeled "Alpha Preview" by its own docs, not a hypothetical one."""
    _require_binary()
    config.require_credentials()

    full_args = [*args] if "--quiet" in args else [*args, "--quiet"]
    result = subprocess.run(
        ["alpaca", *full_args],
        capture_output=True,
        text=True,
        env=config.cli_env(),
        timeout=30,
    )
    if result.returncode != 0:
        raise AlpacaCLIError(
            f"alpaca {' '.join(args)} failed (exit {result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    stdout = result.stdout.strip()
    if not stdout:
        return None
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as e:
        raise AlpacaCLIError(
            f"could not parse JSON from `alpaca {' '.join(args)}`: {e}\n"
            f"first 500 chars of output: {stdout[:500]}"
        )


def get_account() -> dict:
    return run(["account", "get"])


def get_clock() -> dict:
    """Market clock: {"is_open": bool, "next_open": ..., "next_close": ...}
    (standard Alpaca /v2/clock shape). Used to skip gracefully instead of
    erroring when the market is closed (weekends, holidays)."""
    return run(["clock"])


def list_positions() -> List[dict]:
    data = run(["position", "list"])
    if data is None:
        return []
    if isinstance(data, dict):
        data = data.get("positions", list(data.values())[0] if data else [])
    return data if isinstance(data, list) else []


# Half-width of the strike window requested around spot when hunting for a
# near-the-money contract. 5% is wide enough to always contain several
# strikes on liquid ETFs, narrow enough that the 100-result page never
# truncates before reaching spot (the failure verified on 24/08).
STRIKE_BAND_PCT = 0.05

_OCC_PATTERN = re.compile(r"^[A-Z]+\d{6}[CP]\d{8}$")


def has_open_option_position() -> bool:
    """True if any currently-held position looks like an options contract.
    Checks asset_class first (Alpaca's convention: "us_option" for options);
    falls back to an OCC-style symbol shape (root + 6-digit date + C/P +
    8-digit strike) in case asset_class is named differently by the CLI."""
    for pos in list_positions():
        asset_class = str(pos.get("asset_class", "")).lower()
        symbol = str(pos.get("symbol", ""))
        if "option" in asset_class or _OCC_PATTERN.match(symbol):
            return True
    return False


def get_option_ask_price(option_symbol: str) -> Optional[float]:
    """Best-effort ask price for sizing. Tries a few known field-name shapes
    since the exact CLI output for `data option snapshot` wasn't verifiable
    offline. Returns None if no usable price is found (caller should treat
    that as "skip this trade" rather than guess)."""
    # VERIFIED 24/08 against CLI v0.0.13: the flag is --symbols (plural,
    # comma-separated list, limit 100) -- NOT --symbol. The singular form
    # exits with {"error": "unknown flag: --symbol"}, which parses as valid
    # JSON, so it would have failed *silently* (no ask found -> skip trade).
    data = run(["data", "option", "snapshot", "--symbols", option_symbol])
    if not isinstance(data, dict):
        return None

    # unwrap a possible {"snapshots": {"SYMBOL": {...}}} or {"SYMBOL": {...}} wrapper
    candidate = data
    if "snapshots" in data and isinstance(data["snapshots"], dict):
        candidate = next(iter(data["snapshots"].values()), {})
    elif option_symbol in data:
        candidate = data[option_symbol]

    for path in (
        # VERIFIED 24/08 against CLI v0.0.13 on SPY260831C00675000: the real
        # shape is {"snapshots": {SYM: {"latestQuote": {"ap": 88.89, ...}}}}.
        # This exact pair (camelCase parent + short key) was the one
        # combination MISSING from the original guess list, which tried
        # latestQuote/askPrice and latest_quote/ap but never latestQuote/ap.
        ("latestQuote", "ap"),
        ("latest_quote", "ask_price"),
        ("latestQuote", "askPrice"),
        ("latest_quote", "ap"),
        ("ask_price",),
        ("askPrice",),
    ):
        node = candidate
        for key in path:
            if not isinstance(node, dict) or key not in node:
                node = None
                break
            node = node[key]
        if isinstance(node, (int, float)) and node > 0:
            return float(node)
    return None


def _extract_bars(data: Any) -> List[dict]:
    """Handle both known REST shapes: {"bars": [...]} (single-symbol) and
    {"bars": {"SYMBOL": [...]}} (multi-symbol)."""
    bars_field = data.get("bars") if isinstance(data, dict) else data
    if isinstance(bars_field, dict):
        bars_field = next(iter(bars_field.values()), [])
    if not isinstance(bars_field, list):
        raise AlpacaCLIError(f"unexpected bars response shape: {type(bars_field)}")
    return bars_field


def get_daily_bars(symbol: str, lookback_days: int = MIN_TRADING_DAYS_FOR_SWEEP) -> List[Bar]:
    """lookback_days is in *trading* days, not calendar days — the default
    is vol_strategy.MIN_TRADING_DAYS_FOR_SWEEP, not an arbitrary round
    number, because the sweep's largest HV window silently gets zero usable
    score samples if fewer days than that are fetched (verified by
    simulation; see that constant's docstring for the exact failure it
    fixes). The *1.6 below converts the trading-day request into a calendar-
    day date range for the API call, with a small buffer for weekends/holidays."""
    start = (datetime.utcnow() - timedelta(days=int(lookback_days * 1.6) + 10)).strftime("%Y-%m-%d")
    data = run(["data", "bars", "--symbol", symbol, "--start", start, "--timeframe", "1Day"])
    rows = _extract_bars(data)
    bars = []
    for row in rows:
        close = row.get("c", row.get("close"))
        if close is not None:
            bars.append(Bar(close=float(close)))
    return bars


def get_last_price(symbol: str) -> float:
    bars = get_daily_bars(symbol, lookback_days=5)
    if not bars:
        raise AlpacaCLIError(f"no recent bars for {symbol}")
    return bars[-1].close


def find_near_the_money_contract(
    underlying: str,
    direction: int,
    min_days_out: int = 7,
    max_days_out: int = 21,
) -> Optional[str]:
    """direction=+1 -> call, direction=-1 -> put. Uses the raw `alpaca api`
    passthrough (rather than guessing subcommand flag names for options
    contract filtering) so all the REST API's real query params are
    available: underlying_symbols, status, type, expiration_date_gte/lte."""
    spot = get_last_price(underlying)
    contract_type = "call" if direction > 0 else "put"
    today = datetime.utcnow().date()
    gte = (today + timedelta(days=min_days_out)).isoformat()
    lte = (today + timedelta(days=max_days_out)).isoformat()

    # VERIFIED 24/08 against the real API: /v2/options/contracts pages at 100
    # results sorted by strike ASCENDING. Unbounded, the first page for SPY
    # came back as strikes 420..675 while spot was 762.98 -- the spot wasn't
    # even inside the page, so "closest to spot" silently returned the last
    # strike on the page (88 points deep ITM, ~$8,926 of premium). With the
    # 1%-of-equity cap that sizes to qty=0, i.e. the agent would have refused
    # every trade forever while looking like it was working. Bounding the
    # strikes around spot is what makes "near the money" actually mean it.
    lo = round(spot * (1.0 - STRIKE_BAND_PCT), 2)
    hi = round(spot * (1.0 + STRIKE_BAND_PCT), 2)
    query = (
        f"/v2/options/contracts?underlying_symbols={underlying}&status=active"
        f"&type={contract_type}&expiration_date_gte={gte}&expiration_date_lte={lte}"
        f"&strike_price_gte={lo}&strike_price_lte={hi}&limit=100"
    )
    data = run(["api", "GET", query])
    contracts = data.get("option_contracts", []) if isinstance(data, dict) else []
    if not contracts:
        return None

    closest = min(contracts, key=lambda c: abs(float(c["strike_price"]) - spot))
    return closest["symbol"]


def close_position(symbol: str) -> Any:
    return run(["position", "close", "--symbol", symbol])


def submit_paper_option_order(option_symbol: str, qty: int = 1) -> str:
    result = run(
        [
            "order", "submit",
            "--symbol", option_symbol,
            "--side", "buy",
            "--qty", str(qty),
            "--type", "market",
        ]
    )
    if not isinstance(result, dict) or "id" not in result:
        raise AlpacaCLIError(f"order submit returned no order id: {result}")
    return result["id"]
