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
close, "bars" nested by symbol) — flagged explicitly during a real-terminal test pass
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


# The exact CLI build every flag name in this file was verified against, by
# actually running the commands (see the "VERIFIED 24/08" comments below).
# Checked once per process in _check_cli_version(), because "verified against
# v0.0.13" written only in a comment is a policy in prose that nothing
# enforces -- precisely what this project exists to catch elsewhere.
#
# This is not hypothetical: flag drift cost two real bugs on 24/08 alone
# (`data option snapshot --symbol` -> `--symbols`, and `position close
# --symbol` -> `--symbol-or-asset-id`), and BOTH failed quietly -- the first
# returns None and the trade is skipped "because it couldn't be priced", the
# second leaves a stop-lossed position open. A loud warning at the top of a
# run is what turns the next such drift into five minutes instead of a
# silent week.
VERIFIED_CLI_VERSION = "0.0.13"
_version_checked = False


class AlpacaCLIError(Exception):
    """Raised when the `alpaca` CLI exits non-zero or returns unparseable output."""


class DataQualityError(Exception):
    """Raised when the CLI call SUCCEEDED but the data it returned looks
    wrong -- a different failure category from AlpacaCLIError on purpose,
    so it's never confused with a network/auth/CLI problem in a log line.

    Added 24/08, second pass, after external research (an Alpaca-published
    reference architecture and a separate trading-agent architecture guide)
    independently named "silent data feed failure" as a real failure mode:
    "the feed does not error; it stops updating. The agent trades
    confidently on a frozen picture." Nothing in this codebase checked for
    that before -- evaluate_symbol() trusted every bar it got back. Callers
    (agent.py's evaluate_symbol) already wrap the whole per-symbol body in
    try/except Exception, so raising this here turns "trade blind on bad
    data" into "skip this symbol today with a clear reason", the same
    pattern already used for a leak-check failure or a regime that isn't
    cheap -- a normal, logged refusal, not a crash."""


def _require_binary() -> None:
    if shutil.which("alpaca") is None:
        raise AlpacaCLIError(
            "The `alpaca` CLI is not on PATH. Install it with "
            "`brew install alpacahq/tap/cli` (macOS) or "
            "`go install github.com/alpacahq/cli/cmd/alpaca@latest`, then retry.\n"
            "Run `alpaca doctor` after installing to verify."
        )


def _check_cli_version() -> None:
    """Warn once per process if the installed CLI isn't the build the flag
    names here were verified against. Warns, never blocks: a patch release is
    usually harmless, and refusing to trade over a version string would be a
    worse failure than the drift it guards against. Costs one extra
    subprocess per process, not per call."""
    global _version_checked
    if _version_checked:
        return
    _version_checked = True  # set first: a failure here must never retry on every call
    try:
        result = subprocess.run(["alpaca", "version"], capture_output=True, text=True,
                                env=config.cli_env(), timeout=15)
        installed = result.stdout.strip().split()[-1] if result.stdout.strip() else ""
    except Exception:
        return  # version unreadable is not a reason to stop; run() will fail loudly anyway
    if installed and installed != VERIFIED_CLI_VERSION:
        print(
            f"WARNING: alpaca CLI is v{installed}, but every flag name in alpaca_cli.py was "
            f"verified against v{VERIFIED_CLI_VERSION}. Flag drift between builds has already "
            "caused silent failures here (a trade skipped as 'unpriceable', a stop-lossed "
            "position left open). Re-check `alpaca <cmd> --help` for the commands used in this "
            "file before trusting a run.",
            flush=True,
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
    _check_cli_version()

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
        payload = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise AlpacaCLIError(
            f"could not parse JSON from `alpaca {' '.join(args)}`: {e}\n"
            f"first 500 chars of output: {stdout[:500]}"
        )

    # AJOUTE le 26/08/2026. Jusqu'ici, seul le CODE DE SORTIE decidait s'il y
    # avait erreur. Or le CLI a une forme d'erreur documentee dans sa sortie
    # elle-meme -- `{"code": 0, "error": "could not reach ..."}`, vue telle
    # quelle dans decision_log.jsonl. Rien ne garantit que ce corps arrive
    # TOUJOURS avec un code de sortie non nul.
    #
    # CE QUE COUTERAIT L'OUBLI, trace bout en bout:
    #   get_clock()      -> rend le dict d'erreur; `.get("is_open", False)`
    #                       vaut False; monitor_exits conclut "market closed,
    #                       nothing to monitor", journalise outcome
    #                       "market_closed" et NON "error", et la banniere du
    #                       tableau de bord affiche 🟢 "healthy (market was
    #                       closed at last check)".
    #                       Une API injoignable devient un marche ferme, et la
    #                       page dit VERT.
    #   list_positions() -> le dict n'a pas de cle "positions", la valeur de
    #                       repli n'est pas une liste, la fonction rend [].
    #                       "Aucune position ouverte" -- donc manage_exits ne
    #                       verifie AUCUN stop-loss.
    #
    # Les deux degradent en silence, du cote dangereux, dans le seul mecanisme
    # qui protege une position ouverte.
    #
    # PORTEE HONNETE: le cas observe sortait en code 1, donc etait deja
    # attrape. Ce correctif ferme un chemin LATENT, il ne corrige pas une
    # panne constatee. Il est pose parce que le cout d'avoir tort est
    # exactement le mode de panne que ce projet existe pour empecher, et
    # parce qu'une valeur qu'on ne sait pas interpreter n'est pas une
    # permission de supposer.
    #
    # Seule une valeur VRAIE declenche: une charge legitime portant
    # `"error": null` ou `"error": ""` reste une reponse valide.
    if isinstance(payload, dict) and payload.get("error"):
        raise AlpacaCLIError(
            f"`alpaca {' '.join(args)}` exited {result.returncode} but returned an "
            f"error payload: {payload.get('error')!r}"
        )
    return payload


def get_account() -> dict:
    return run(["account", "get"])


def get_clock() -> dict:
    """Market clock: {"is_open": bool, "next_open": ..., "next_close": ...}
    (standard Alpaca /v2/clock shape). Used to skip gracefully instead of
    erroring when the market is closed (weekends, holidays)."""
    return run(["clock"])


def list_positions() -> List[dict]:
    """Positions ouvertes. Leve plutot que de rendre [] sur une reponse
    inexploitable.

    CORRIGE le 26/08/2026. La derniere ligne etait
    `return data if isinstance(data, list) else []`: toute reponse que cette
    fonction ne savait pas lire devenait "aucune position ouverte".

    C'est le pire repli possible ICI precisement. `manage_exits()` boucle sur
    ce que rend cette fonction: une liste vide veut dire "rien a surveiller",
    donc AUCUN stop-loss n'est verifie. Et comme Alpaca ne supporte pas les
    ordres bracket/OCO sur options -- verifie contre la vraie API -- cette
    boucle est le seul mecanisme protegeant une position ouverte. Un malentendu
    de format se serait traduit par une position reelle laissee sans
    surveillance, sans une ligne de journal pour le dire.

    "Je n'ai pas compris la reponse" n'est pas "il n'y a rien". Un vrai vide --
    stdout vide, ou une liste vide -- reste bien sur un vide legitime.
    """
    data = run(["position", "list"])
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        positions = data.get("positions")
        if isinstance(positions, list):
            return positions
        if not data:
            return []
    raise AlpacaCLIError(
        "could not read the position list from `alpaca position list`: expected a "
        f"list, or a dict with a 'positions' list, got {type(data).__name__} "
        f"with keys {sorted(data)[:6] if isinstance(data, dict) else '(n/a)'}. "
        "Refusing to report 'no open positions' from a response this function "
        "does not understand -- that would silently skip every stop-loss check."
    )


# Half-width of the strike window requested around spot when hunting for a
# near-the-money contract. 5% is wide enough to always contain several
# strikes on liquid ETFs, narrow enough that the 100-result page never
# truncates before reaching spot (the failure verified on 24/08).
STRIKE_BAND_PCT = 0.05

_OCC_PATTERN = re.compile(r"^[A-Z]+\d{6}[CP]\d{8}$")
_OCC_ROOT_PATTERN = re.compile(r"^([A-Z]+)\d{6}[CP]\d{8}$")


def is_option_position(pos: dict) -> bool:
    """Checks asset_class first (Alpaca's convention: "us_option" for
    options); falls back to an OCC-style symbol shape (root + 6-digit date +
    C/P + 8-digit strike) in case asset_class is named differently by the CLI."""
    asset_class = str(pos.get("asset_class", "")).lower()
    symbol = str(pos.get("symbol", ""))
    return "option" in asset_class or bool(_OCC_PATTERN.match(symbol))


def has_open_option_position() -> bool:
    """True if any currently-held position looks like an options contract.
    Kept for backward compatibility; risk_gates.py now uses
    list_open_option_positions() + option_underlying() for the per-underlying,
    multi-position gate (see risk_gates.py, added 24/08 to support trading
    several uncorrelated symbols concurrently instead of one at a time)."""
    return any(is_option_position(pos) for pos in list_positions())


def list_open_option_positions() -> List[dict]:
    """All currently-held positions that look like options contracts."""
    return [pos for pos in list_positions() if is_option_position(pos)]


def option_underlying(pos: dict) -> Optional[str]:
    """The underlying stock symbol for an option position, e.g. "SPY" for
    SPY260831P00763000. Tries the `underlying_symbol` field first (present on
    Alpaca's option-contract objects; not yet verified whether the CLI's
    `position list` output includes it too), falls back to parsing the OCC
    symbol's root -- which always works since every option position symbol
    is OCC-formatted."""
    underlying = pos.get("underlying_symbol")
    if underlying:
        return str(underlying).upper()
    match = _OCC_ROOT_PATTERN.match(str(pos.get("symbol", "")))
    return match.group(1) if match else None


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


MAX_STALE_DAYS = 5           # refuse to trade if the most recent bar is older than this (calendar days)
MAX_DAILY_JUMP_PCT = 0.50    # refuse to trade if any adjacent-day close moves more than this -- likely bad data, not a real move, for a liquid sector ETF


def _check_bar_quality(symbol: str, rows: List[dict], minimum_usable: Optional[int] = None) -> None:
    """Raises DataQualityError instead of silently handing bad data to the
    strategy layer. Two checks, both deliberately generous (long weekends,
    holidays, and real market moves all need to pass without a false
    alarm) -- the goal is catching a frozen/corrupted feed, not being
    twitchy about ordinary volatility."""
    if not rows:
        raise DataQualityError(f"{symbol}: no bars returned at all")

    last_ts_raw = rows[-1].get("t")
    if last_ts_raw:
        try:
            last_ts = datetime.fromisoformat(str(last_ts_raw).replace("Z", "+00:00"))
            age_days = (datetime.now(last_ts.tzinfo) - last_ts).total_seconds() / 86400
            if age_days > MAX_STALE_DAYS:
                raise DataQualityError(
                    f"{symbol}: most recent bar is {age_days:.1f} days old (timestamp {last_ts_raw}), "
                    f"> {MAX_STALE_DAYS}-day staleness limit -- feed may be frozen, refusing to trade on it"
                )
        except ValueError:
            print(f"  WARNING: {symbol}: could not parse bar timestamp {last_ts_raw!r}, skipping staleness check")

    closes = [row.get("c", row.get("close")) for row in rows]
    closes = [float(c) for c in closes if c is not None]

    # AJOUTE le 27/08/2026. Les deux controles ci-dessus attrapent un feed GELE
    # (barre la plus recente trop vieille) et un feed CORROMPU (saut de prix
    # invraisemblable). Aucun n'attrapait un feed TRONQUE.
    #
    # Ce compte-la est celui des clotures REELLEMENT exploitables, pas des
    # lignes rendues : get_daily_bars() ecarte silencieusement toute ligne sans
    # prix de cloture, et la ligne juste au-dessus fait pareil ici.
    #
    # Pourquoi ca compte, mesure le 27/08 : avec 325 barres au lieu des 592 que
    # MIN_TRADING_DAYS_FOR_SWEEP exige, la fenetre HV de 90 jours obtient ZERO
    # echantillon. hindsight_guard refuse desormais de certifier dans ce cas
    # (voir _sharpe, corrige le meme jour), mais son diagnostic parle de
    # « fenetres 20, 60, 90 non notables » -- vrai, et illisible pour qui
    # cherche la cause. Ici on peut dire la chose : il manque des barres.
    #
    # Un symbole dont l'historique est plus court que la fenetre de balayage
    # n'est pas un symbole a traiter avec precaution, c'est un symbole sur
    # lequel ce balayage ne veut rien dire.
    if minimum_usable is not None and len(closes) < minimum_usable:
        raise DataQualityError(
            f"{symbol}: only {len(closes)} usable daily closes returned, need at least "
            f"{minimum_usable} for the parameter sweep to score every candidate window "
            f"(vol_strategy.MIN_TRADING_DAYS_FOR_SWEEP). A shorter history makes the "
            f"largest HV windows unscorable, so the selection would be made among "
            f"candidates that were never actually measured -- refusing rather than "
            f"sweeping on it."
        )

    # AJOUTE le 27/08/2026. Un prix de cloture NUL OU NEGATIF est impossible
    # pour un ETF : c'est une donnee corrompue, sans ambiguite.
    #
    # Personne ne le signalait, et deux endroits l'evitaient chacun de leur
    # cote sans le dire :
    #   - la boucle ci-dessous fait `if prev == 0: continue`, donc un zero
    #     n'est jamais compare a son voisin ;
    #   - vol_strategy.daily_returns() filtre `if closes[i-1] != 0`, donc le
    #     point est ECARTE de la serie de rendements.
    # Resultat : une barre a zero traversait le controle qualite, puis
    # disparaissait de la serie en recollant artificiellement les deux jours qui
    # l'entourent -- un rendement invente, sur des donnees dont on sait qu'elles
    # sont fausses.
    #
    # On refuse, plutot que d'eviter chacun dans son coin.
    for i, c in enumerate(closes):
        if c <= 0:
            raise DataQualityError(
                f"{symbol}: bar {i} has a close of {c} -- a non-positive price is "
                f"impossible for a tradable ETF, so this feed is corrupted. Refusing "
                f"rather than silently dropping the point from the return series."
            )

    for i in range(1, len(closes)):
        prev = closes[i - 1]
        if prev == 0:
            continue  # inatteignable depuis le controle ci-dessus ; garde-fou
        jump = abs(closes[i] - prev) / prev
        if jump > MAX_DAILY_JUMP_PCT:
            raise DataQualityError(
                f"{symbol}: bar {i} moved {jump:.1%} from the previous close (${prev:.2f} -> ${closes[i]:.2f}), "
                f"> {MAX_DAILY_JUMP_PCT:.0%} single-day sanity limit -- likely bad data (or an unhandled "
                f"split/reverse-split), refusing to trade on it without a human checking first"
            )


def get_daily_bars(symbol: str, lookback_days: int = MIN_TRADING_DAYS_FOR_SWEEP) -> List[Bar]:
    """lookback_days is in *trading* days, not calendar days — the default
    is vol_strategy.MIN_TRADING_DAYS_FOR_SWEEP, not an arbitrary round
    number, because the sweep's largest HV window silently gets zero usable
    score samples if fewer days than that are fetched (verified by
    simulation; see that constant's docstring for the exact failure it
    fixes). The *1.6 below converts the trading-day request into a calendar-
    day date range for the API call, with a small buffer for weekends/holidays.

    Raises DataQualityError (see _check_bar_quality) if the returned bars
    look stale or contain an implausible price jump -- checked here, once,
    so every caller (vol_strategy, momentum_strategy, backtest.py,
    compare_strategies.py) gets the same protection for free instead of
    each needing to remember to check."""
    start = (datetime.utcnow() - timedelta(days=int(lookback_days * 1.6) + 10)).strftime("%Y-%m-%d")
    data = run(["data", "bars", "--symbol", symbol, "--start", start, "--timeframe", "1Day"])
    rows = _extract_bars(data)
    _check_bar_quality(symbol, rows, minimum_usable=lookback_days)
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
    spot: Optional[float] = None,
) -> Optional[str]:
    """direction=+1 -> call, direction=-1 -> put. Uses the raw `alpaca api`
    passthrough (rather than guessing subcommand flag names for options
    contract filtering) so all the REST API's real query params are
    available: underlying_symbols, status, type, expiration_date_gte/lte."""
    # spot is passed in by agent.py, which already fetched this symbol's bars
    # in evaluate_symbol() -- without it, get_last_price() spawns a SECOND
    # `alpaca data bars` subprocess for the same symbol purely to read the
    # last close the caller is already holding. Kept optional so the function
    # still stands alone (backtest/manual use).
    if spot is None:
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

    # AJOUTE le 27/08/2026. Cette cle ne regardait QUE le strike. La requete
    # ci-dessus couvre 7 a 21 jours, et un sous-jacent liquide comme SPY a des
    # echeances lundi/mercredi/vendredi : une demi-douzaine de contrats
    # partagent donc EXACTEMENT le meme strike. min() rend alors le premier de
    # la liste, c'est-a-dire ce que l'ordre de la reponse decide.
    #
    # Mesure, meme spot, memes contrats, meme strike retenu (500.00) :
    #     ordre API croissant   -> echeance 2026-09-02   (2 jours)
    #     ordre API inverse     -> echeance 2026-09-15   (15 jours)
    #     ordre API quelconque  -> echeance 2026-09-11   (11 jours)
    #
    # L'API documente un tri par strike CROISSANT ; elle ne dit rien de l'ordre
    # a strike egal. La valeur temps de ce qui est achete -- donc le theta paye
    # chaque jour -- dependait d'un detail non specifie, sur CHAQUE transaction.
    #
    # DECISION A CONFIRMER PAR UN HUMAIN, ecrite ici plutot que subie : a
    # egalite de strike on prend l'echeance la PLUS PROCHE. C'est ce que l'ordre
    # naturel des symboles produisait deja en pratique (donc le changement de
    # comportement attendu est nul dans le cas courant), et c'est ce qui colle
    # le mieux au modele que backtest.py simule -- un payoff a UN JOUR
    # (`abs(rets[next_day_ret_index])`). Le revers est assume : echeance proche
    # = gamma eleve mais theta le plus rapide. Si la strategie doit privilegier
    # le temps plutot que la convexite, c'est ICI que ca se change, et ce doit
    # etre un choix explicite -- pas un effet de bord de l'ordre de pagination.
    #
    # `symbol` en dernier rang garantit un resultat totalement deterministe meme
    # si deux contrats partageaient strike ET echeance.
    closest = min(
        contracts,
        key=lambda c: (abs(float(c["strike_price"]) - spot),
                       str(c.get("expiration_date", "")),
                       str(c.get("symbol", ""))),
    )
    return closest["symbol"]


def close_position(symbol: str) -> Any:
    """VERIFIED 24/08 against CLI v0.0.13 by actually closing a live paper
    position: the flag is --symbol-or-asset-id, NOT --symbol. The wrong form
    exits 1 with {"error": "unknown flag: --symbol"}, which run() turns into
    an AlpacaCLIError -- meaning manage_exits() would have raised every time
    a take-profit or stop-loss actually fired. This is the one branch mocks
    could never catch, and it sat in the risk system, not a nice-to-have."""
    return run(["position", "close", "--symbol-or-asset-id", symbol])


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
