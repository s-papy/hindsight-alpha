# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha
#
# Sous licence MIT, redistribuer ce fichier -- entier ou par morceaux --
# OBLIGE a conserver cet avis. C'est la seule contrainte de la licence, et
# c'est la raison d'etre de ces trois lignes : un fichier copie-colle
# emporte desormais sa provenance avec lui.

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
   attached, driving it interactively).

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
import math
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

import config
import decision_log
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
    erroring when the market is closed (weekends, holidays).

    DURCI le 27/08/2026, la veille du kickoff. Les deux appelants faisaient
    `clock.get("is_open", False)` -- agent.py ligne ~334, monitor_exits.py.
    Une reponse JSON parfaitement VALIDE mais depourvue de ce champ faisait
    donc conclure « marche ferme » : l'agent sautait la journee entiere,
    journalisait `market_closed`, et le tableau de bord affichait un badge
    gris parfaitement routinier.

    Sur une semaine jugee qui ne compte que cinq jours de bourse, une journee
    perdue en silence est chere -- et rien ne dirait pourquoi.

    Meme raisonnement que list_positions() le 26/08 : « je n'ai pas compris
    la reponse » n'est pas « il n'y a rien ». run() leve deja sur un CORPS
    d'erreur, mais pas sur une reponse valide dont le champ aurait ete
    renomme -- et ce fichier documente DEUX surprises de nommage de ce CLI en
    « Alpha Preview » (--symbols au pluriel, --symbol-or-asset-id).

    Le SENS de l'echec compte : lever fait journaliser `error`, VISIBLE, au
    lieu de `market_closed`, invisible. Un agent qui s'arrete en disant
    pourquoi vaut mieux qu'un agent qui ne trade pas sans le dire.

    Un booleen est exige, pas une valeur « vraie » : la chaine "false" est
    vraie en Python, et l'accepter transformerait un marche ferme en marche
    ouvert."""
    data = run(["clock"])
    if not isinstance(data, dict) or not isinstance(data.get("is_open"), bool):
        raise AlpacaCLIError(
            "could not read the market clock: expected a dict with a boolean "
            "'is_open', got %s. Refusing to read this as 'the market is "
            "closed' -- that would silently skip a whole trading day."
            % (sorted(data)[:6] if isinstance(data, dict) else type(data).__name__)
        )
    return data


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

# La taille de page demandee a /v2/options/contracts. Constante nommee depuis
# le 27/08 : elle etait ecrite en dur dans l'URL, et la detection de troncature
# ajoutee le meme jour doit comparer au MEME nombre. Deux 100 independants,
# c'est un jour ou l'un des deux bouge seul.
CONTRACTS_PAGE_LIMIT = 100

# CORRIGE le 27/08/2026. Ces motifs n'acceptaient que la forme COMPACTE.
# Or la specification OCC definit un symbole de 21 caracteres dont la racine
# est COMPLETEE PAR DES ESPACES a six caracteres : « SPY   260831P00764000 ».
# Alpaca rend generalement la forme compacte, mais rien ne le garantit -- et
# ce fichier documente lui-meme son incertitude sur les champs rendus par le
# CLI, quelques lignes plus haut.
#
# Consequence mesuree de bout en bout, MEME position, deux ecritures :
#     OCC compact  -> check_gates refuse : « already holding ... on SPY »
#     OCC standard -> check_gates AUTORISE un 2e SPY, 3 contrats
# C'est-a-dire la regle « jamais deux positions sur le meme sous-jacent »,
# annoncee dans le deck, le write-up et le script video.
#
# On normalise aussi la casse : un symbole en minuscules echouait des deux
# cotes, et le mettre en majuscules ne peut creer aucun faux positif -- une
# chaine qui a la FORME d'un symbole OCC en est un.
_OCC_PATTERN = re.compile(r"^[A-Z]+ *\d{6}[CP]\d{8}$")
_OCC_ROOT_PATTERN = re.compile(r"^([A-Z]+) *\d{6}[CP]\d{8}$")


def is_option_position(pos: dict) -> bool:
    """Checks asset_class first (Alpaca's convention: "us_option" for
    options); falls back to an OCC-style symbol shape (root + 6-digit date +
    C/P + 8-digit strike) in case asset_class is named differently by the CLI."""
    asset_class = str(pos.get("asset_class", "")).lower()
    symbol = str(pos.get("symbol", "")).upper()
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
    match = _OCC_ROOT_PATTERN.match(str(pos.get("symbol", "")).upper())
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

    # LA CLE EST VERIFIEE, PAS SUPPOSEE. Ajoute le 30/08/2026.
    #
    # Cette ligne etait `next(iter(data["snapshots"].values()), {})` : elle
    # prenait le PREMIER snapshot sans jamais regarder de quel contrat il
    # parlait. C'est mot pour mot le defaut corrige le 27/08 dans
    # `_extract_bars`, quarante lignes plus bas, dont la docstring dit « la
    # consequence est la pire de ce depot ». La lecon avait ete appliquee aux
    # barres et pas au snapshot d'option, dans le meme fichier.
    #
    # Et ici elle coute plus cher que la pour une raison arithmetique : cet
    # ask DIMENSIONNE la position. `qty = per_trade_dollars // (ask * 100)`.
    # Mesure du 30/08 sur l'equite reelle (99 961,91 $, plafond 1 %) :
    #
    #     ask lu 3.74 (le bon contrat)      ->   2 contrats ->    748 $  0,7 %
    #     ask lu 0.50 (un autre contrat)    ->  19 contrats ->  7 106 $  7,1 %
    #     ask lu 0.05 (un contrat lointain) -> 199 contrats -> 74 426 $ 74,5 %
    #
    # Un ask lu sur le mauvais contrat ne fait donc pas payer un peu trop :
    # il fait sauter TOUS les plafonds a la fois, en restant vert.
    #
    # ATTEIGNABILITE NON DEMONTREE, comme pour `_extract_bars` : l'appel passe
    # --symbols avec UN seul symbole, donc une API qui se comporte bien ne
    # peut rendre que celui-la. Le cout du controle est de trois lignes.
    #
    # Comparaison insensible a la casse, meme raison que son jumeau : refuser
    # « spy... » face a « SPY... » serait un faux positif.
    candidate = data
    if "snapshots" in data and isinstance(data["snapshots"], dict):
        par_cle = {str(k).upper(): v for k, v in data["snapshots"].items()}
        attendu = str(option_symbol).upper()
        if attendu not in par_cle:
            raise AlpacaCLIError(
                "option snapshot is keyed by symbol but does not contain the "
                "one that was requested: asked for %r, got %s. Refusing to "
                "size a position on another contract's ask -- that price "
                "decides the quantity, so a cheaper contract's ask would "
                "blow through every exposure cap while every gate stayed "
                "green."
                % (option_symbol,
                   ", ".join(repr(k) for k in sorted(data["snapshots"]))
                   or "(none)"))
        candidate = par_cle[attendu]
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


def _extract_bars(data: Any, expected_symbol: Optional[str] = None) -> List[dict]:
    """Handle both known REST shapes: {"bars": [...]} (single-symbol) and
    {"bars": {"SYMBOL": [...]}} (multi-symbol).

    CORRIGE le 27/08/2026. Sur la forme a dictionnaire, cette fonction prenait
    la PREMIERE valeur -- `next(iter(bars_field.values()), [])` -- sans jamais
    regarder la cle. Reproduit : une reponse portant « GLD » pour une demande
    « SPY » rendait 700 barres d'or, sans erreur ni avertissement.

    La consequence est la pire de ce depot : SPY aurait ete evalue, note par
    hindsight_guard et trade sur des prix d'or, et RIEN n'aurait pu le
    signaler. Le garde de fuite tourne parfaitement sur des donnees qui ne
    sont pas les bonnes -- il verifie la methode, jamais l'identite de ce
    qu'on lui donne.

    ATTEIGNABILITE NON DEMONTREE : l'appel passe --symbol, donc une API qui se
    comporte bien ne peut renvoyer que ce symbole-la. Mais ce fichier
    documente DEJA deux surprises de nommage de ce CLI en « Alpha Preview »
    (--symbols au pluriel pour les snapshots d'options, --symbol-or-asset-id
    pour la cloture), et une reponse multi-symboles rendait ici un symbole
    ARBITRAIRE, decide par l'ordre du dictionnaire. Le cout du controle est
    d'une ligne ; celui de son absence est de trader le mauvais instrument.

    La comparaison ignore la casse : refuser « spy » face a « SPY » serait un
    faux positif, et un controle qui crie sur du normal s'apprend a ignorer.
    La forme SANS dictionnaire n'a aucune cle a verifier et reste acceptee
    telle quelle -- exiger une cle partout casserait la forme mono-symbole."""
    bars_field = data.get("bars") if isinstance(data, dict) else data
    if isinstance(bars_field, dict):
        if expected_symbol is not None:
            correspond = {str(k).upper(): v for k, v in bars_field.items()}
            attendu = str(expected_symbol).upper()
            if attendu not in correspond:
                raise AlpacaCLIError(
                    "bars response is keyed by symbol but does not contain the "
                    "one that was requested: asked for %r, got %s. Refusing to "
                    "trade %s on another instrument's prices -- every check "
                    "downstream (including hindsight_guard) would run happily "
                    "on the wrong data."
                    % (expected_symbol,
                       ", ".join(repr(k) for k in sorted(bars_field)) or "(none)",
                       expected_symbol)
                )
            bars_field = correspond[attendu]
        else:
            bars_field = next(iter(bars_field.values()), [])
    if not isinstance(bars_field, list):
        raise AlpacaCLIError(f"unexpected bars response shape: {type(bars_field)}")
    return bars_field


MAX_STALE_DAYS = 5           # refuse to trade if the most recent bar is older than this (calendar days)


def _horodatage_utc(brut: object) -> "datetime | None":
    """Alias vers `decision_log.en_utc`, ou vit desormais la regle et tout
    son raisonnement -- y compris la mesure par fuseau de la porte de
    fraicheur. Ce fichier en avait une copie au corps identique a celle de
    `bilan_semaine` -- fusionnees le 30/08/2026."""
    return decision_log.en_utc(brut)


MAX_IDENTICAL_CLOSES = 5     # a liquid ETF does not print the same close a full trading week running
MAX_DAILY_JUMP_PCT = 0.50    # refuse to trade if any adjacent-day close moves more than this -- likely bad data, not a real move, for a liquid sector ETF


def _check_bar_quality(symbol: str, rows: List[dict], minimum_usable: Optional[int] = None) -> None:
    """Raises DataQualityError instead of silently handing bad data to the
    strategy layer. Two checks, both deliberately generous (long weekends,
    holidays, and real market moves all need to pass without a false
    alarm) -- the goal is catching a frozen/corrupted feed, not being
    twitchy about ordinary volatility."""
    if not rows:
        raise DataQualityError(f"{symbol}: no bars returned at all")

    # AJOUTE le 27/08/2026. RIEN ne verifiait que les barres arrivent dans
    # l'ordre chronologique, alors que TOUT en depend : daily_returns() fait
    # closes[i] - closes[i-1], et surtout score_hv_window() decoupe
    # `bars[:len - IN_SAMPLE_HOLDOUT_DAYS]` en appelant ca « tout sauf les 20
    # derniers jours » -- ce qui n'est vrai que si la liste est triee.
    #
    # Autrement dit, la correction du test de FUITE, qui est la these entiere
    # de ce projet, reposait sur une hypothese jamais verifiee.
    #
    # Mesure avant ce controle :
    #     ordre chronologique          -> accepte  (juste)
    #     ordre INVERSE                -> refuse, mais « feed may be frozen » :
    #                                     diagnostic FAUX, le flux n'est pas
    #                                     gele, il est a l'envers
    #     deux barres permutees        -> ACCEPTE
    #     les deux DERNIERES permutees -> ACCEPTE  <- la frontiere du holdout
    #
    # Le desordre partiel passait donc tout, en silence. Les horodatages
    # illisibles sont ignores ici, pas refuses : le controle de fraicheur
    # juste en dessous fait deja ce choix et le documente.
    precedent = None
    for i, ligne in enumerate(rows):
        brut = ligne.get("t")
        if not brut:
            continue
        ts = _horodatage_utc(brut)
        if ts is None:
            continue
        if precedent is not None and ts < precedent[1]:
            raise DataQualityError(
                "%s: bars are not in chronological order -- row %d (%s) is "
                "OLDER than row %d (%s). Every return, every volatility window "
                "and the in-sample/full split of the leak check assume this "
                "list is sorted oldest-first; refusing to compute on it."
                % (symbol, i, brut, precedent[0], precedent[2]))
        precedent = (i, ts, brut)

    last_ts_raw = rows[-1].get("t")
    if last_ts_raw:
        last_ts = _horodatage_utc(last_ts_raw)
        if last_ts is None:
            print(f"  WARNING: {symbol}: could not parse bar timestamp {last_ts_raw!r}, skipping staleness check")
        else:
            age_days = (datetime.now(timezone.utc) - last_ts).total_seconds() / 86400
            if age_days > MAX_STALE_DAYS:
                raise DataQualityError(
                    f"{symbol}: most recent bar is {age_days:.1f} days old (timestamp {last_ts_raw}), "
                    f"> {MAX_STALE_DAYS}-day staleness limit -- feed may be frozen, refusing to trade on it"
                )

    # AJOUTE le 27/08/2026 : « exploitable » exige desormais un nombre FINI.
    #
    # Mesure avant correctif, sur 700 barres :
    #     saut de prix x9        -> refuse   (juste)
    #     UNE barre a « nan »    -> ACCEPTE
    #     TOUTES a « nan »       -> ACCEPTE
    #
    # Cette porte existe pour refuser des donnees inexploitables, et elle
    # laissait passer un flux ou RIEN n'est un nombre. Le NaN defait chacune
    # de ses comparaisons : `abs(nan - prev) / prev > MAX_DAILY_JUMP_PCT` est
    # False, et un NaN comptait comme une cloture exploitable.
    #
    # L'agent ne tradait pas pour autant -- les Sharpe deviennent NaN, donc
    # hindsight_guard refuse en « CANNOT CONCLUDE ». Mais le DIAGNOSTIC etait
    # faux : l'operateur lit « fenetres 10/20/30/60/90 non notables » et
    # cherche du cote de la strategie, alors que le flux de prix est vide de
    # sens. C'est exactement l'argument que le commentaire ci-dessous tient
    # deja pour le flux TRONQUE -- « ici on peut dire la chose ».
    #
    # Une valeur non convertible faisait en plus lever un ValueError nu depuis
    # cette ligne meme, sans nommer le symbole. Elle rejoint les clotures
    # inexploitables, ce que la suite de cette fonction sait deja compter.
    closes = []
    for c in (row.get("c", row.get("close")) for row in rows):
        if c is None:
            continue
        try:
            valeur = float(c)
        except (TypeError, ValueError):
            continue
        if math.isfinite(valeur):
            closes.append(valeur)

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

    # AJOUTE le 27/08/2026. Le controle de flux GELE juste au-dessus ne regarde
    # que l'AGE de la barre la plus recente. Une source qui repete sa derniere
    # cloture pendant que les horodatages continuent d'avancer le traverse
    # intact -- et la deduplication par horodatage (get_daily_bars) ne la voit
    # pas non plus, puisque les dates, elles, sont bien distinctes.
    #
    # Ce n'est pas cosmetique : une cloture repetee donne un rendement de 0%,
    # ce qui fait BAISSER la volatilite mesuree. Or cette strategie entre quand
    # « la volatilite est bon marche ». Mesure sur 700 jours, fenetre HV 30 :
    #
    #     aucun plat (temoin)                 rang HV 81.0  -> s'abstient
    #     3 clotures identiques a la fin      rang HV 71.8  -> s'abstient
    #     10 clotures identiques a la fin     rang HV 63.5  -> s'abstient
    #     30 clotures identiques a la fin     rang HV  0.0  -> ACHETE
    #
    # Degradation monotone, pas un artefact de seuil. Un defaut de donnees qui
    # AUTORISE un trade, pas un qui le refuse.
    #
    # Portee volontairement limitee a la QUEUE de la serie, et cette limite est
    # mesuree, pas supposee : un plat au MILIEU de l'historique abaisse les
    # valeurs HV passees, donc remonte le rang d'aujourd'hui --
    #
    #     30 plats au milieu (j300-330)       rang HV 99.2  -> s'abstient
    #     60 plats au milieu (j200-260)       rang HV 73.8  -> s'abstient
    #
    # -- il pousse vers le refus, du cote sur. Seule la queue retourne la
    # decision vers l'achat.
    #
    # Limite assumee : le reseau sortant est bloque ici, je n'ai donc PAS pu
    # mesurer la longueur des series de clotures identiques sur les vraies
    # donnees SPY/GLD/XLK/XLV. Le seuil est choisi genereux pour cela -- une
    # semaine de bourse entiere au meme centime. Si un ETF liquide declenche
    # cette alerte, c'est le seuil qu'il faut relire, pas l'alerte qu'il faut
    # taire.
    if len(closes) >= MAX_IDENTICAL_CLOSES:
        queue = closes[-MAX_IDENTICAL_CLOSES:]
        if all(c == queue[0] for c in queue):
            raise DataQualityError(
                f"{symbol}: the last {MAX_IDENTICAL_CLOSES} closes are all "
                f"${queue[0]:.2f} -- the timestamps advance but the price does "
                f"not, so this feed is frozen in a way the staleness check "
                f"cannot see. Repeated closes are 0% returns: they push measured "
                f"volatility DOWN, and this strategy buys when volatility looks "
                f"cheap. Refusing rather than trading on a feed that biases "
                f"toward entering."
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
    start = (datetime.now(timezone.utc)
             - timedelta(days=int(lookback_days * 1.6) + 10)).strftime("%Y-%m-%d")
    data = run(["data", "bars", "--symbol", symbol, "--start", start, "--timeframe", "1Day"])
    rows = _extract_bars(data, expected_symbol=symbol)

    # AJOUTE le 27/08/2026, en suite directe du controle d'ordre : celui-ci
    # tolere DELIBEREMENT deux horodatages egaux -- un doublon n'est pas un
    # desordre -- mais rien d'autre ne les attrapait. Mesure sur 700 jours :
    #
    #     aucun doublon        -> 700 lignes / 700 jours reels
    #     100 barres doublees  -> 800 lignes / 700 jours reels, ACCEPTE
    #
    # Deux consequences, et la seconde touche le signal lui-meme :
    #   . `minimum_usable` compte des LIGNES, pas des jours distincts : un flux
    #     tres duplique franchit le seuil d'historique tout en ayant beaucoup
    #     moins d'histoire -- exactement la panne que
    #     MIN_TRADING_DAYS_FOR_SWEEP existe pour empecher ;
    #   . un doublon insere un rendement de 0% (meme cloture deux fois), ce qui
    #     fait BAISSER la volatilite mesuree. Or « la volatilite est bon
    #     marche » est le signal d'entree de cette strategie : des doublons la
    #     poussent donc a trader davantage.
    #
    # On deduplique AVANT le controle de qualite, une seule fois, pour que la
    # porte et le constructeur voient la meme serie -- les faire dedupliquer
    # chacun de leur cote serait la meme regle ecrite deux fois.
    vus, dedupliquees = set(), []
    for ligne in rows:
        cle = ligne.get("t")
        if cle is not None and cle in vus:
            continue
        if cle is not None:
            vus.add(cle)
        dedupliquees.append(ligne)
    if len(dedupliquees) != len(rows):
        print("  WARNING: %s: %d duplicate daily bar(s) removed before "
              "scoring. Duplicates lower measured volatility (a repeated close "
              "is a 0%% return), and this strategy enters when volatility looks "
              "cheap."
              % (symbol, len(rows) - len(dedupliquees)), flush=True)
    rows = dedupliquees

    _check_bar_quality(symbol, rows, minimum_usable=lookback_days)
    # Le constructeur applique la MEME definition d'« exploitable » que la
    # porte de qualite juste au-dessus : un nombre FINI. Avant le 27/08 les
    # deux divergeaient -- la porte tolerait des lignes inexploitables et
    # comptait celles qui restaient, puis cette boucle-ci levait un ValueError
    # nu sur la premiere valeur non convertible, tuant le symbole entier pour
    # une seule mauvaise ligne. Et un NaN, lui, entrait tel quel dans la serie
    # de prix.
    #
    # Deux definitions du meme mot a dix lignes d'ecart : la porte decidait
    # qu'on avait assez de donnees, le constructeur refusait de les fabriquer.
    bars = []
    for row in rows:
        close = row.get("c", row.get("close"))
        if close is None:
            continue
        try:
            valeur = float(close)
        except (TypeError, ValueError):
            continue
        if math.isfinite(valeur):
            bars.append(Bar(close=valeur))
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
    today = datetime.now(timezone.utc).date()
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
        f"&strike_price_gte={lo}&strike_price_lte={hi}&limit={CONTRACTS_PAGE_LIMIT}"
    )
    data = run(["api", "GET", query])
    # DURCI le 27/08/2026, trouve par un balayage AST des 24 lectures avec
    # valeur par defaut sur une reponse externe. La ligne d'origine etait
    # `data.get("option_contracts", []) if isinstance(data, dict) else []`,
    # et SIX reponses differentes donnaient toutes le meme resultat -- une
    # seule etant legitime :
    #
    #     {"option_contracts": []}   -> None   vrai : aucun contrat
    #     {}                         -> None   dict vide
    #     {"contracts": [...]}       -> None   cle renommee
    #     []                         -> None   mauvais type
    #     None                       -> None   reponse nulle
    #
    # En aval, agent.py journalise `no_contract_found` et la page affiche un
    # badge jaune « no contract » d'apparence routiniere. Or pour SPY, GLD,
    # XLK ou XLV, « aucun contrat d'option entre 7 et 21 jours » n'arrive
    # JAMAIS en vrai : c'est toujours le signe qu'on n'a pas compris la
    # reponse. Un symbole saute alors sa journee, en silence.
    #
    # Meme raisonnement que list_positions() et get_clock() : « je n'ai pas
    # compris » n'est pas « il n'y a rien ». Une reponse COMPRISE annoncant
    # zero contrat reste un resultat legitime -- confondre les deux dans
    # l'autre sens ferait echouer des runs parfaitement normaux.
    if not isinstance(data, dict) or not isinstance(data.get("option_contracts"), list):
        raise AlpacaCLIError(
            "could not read the option-contracts response for %s: expected a "
            "dict with an 'option_contracts' list, got %s. Refusing to read "
            "this as 'no contract exists' -- on a liquid ETF that answer is "
            "never true, and it would silently skip this symbol for the day."
            % (underlying,
               sorted(data)[:6] if isinstance(data, dict) else type(data).__name__)
        )
    contracts = data["option_contracts"]
    if not contracts:
        return None

    # AJOUTE le 27/08/2026, en fermant la famille NaN. La cle de tri ci-dessous
    # fait `abs(float(strike) - spot)`, et min() compare avec `<` : TOUTE
    # comparaison impliquant un NaN rend False, donc le PREMIER element reste.
    # Mesure, memes contrats, deux ordres :
    #
    #     [strike "nan", strike "500"]  -> le contrat au strike ILLISIBLE gagne
    #     [strike "500", strike "nan"]  -> le contrat a 500 gagne
    #
    # Le contrat retenu dependait donc de sa POSITION dans la reponse, et un
    # contrat dont on n'a pas su lire le strike pouvait partir a l'ordre.
    # C'est le meme mecanisme que le defaut d'ordre corrige le matin meme dans
    # hindsight_guard, a un autre endroit.
    #
    # On ecarte les strikes illisibles plutot que de les laisser gagner. Si
    # AUCUN n'est lisible alors qu'on a bien recu des contrats, on leve : « je
    # n'ai pas su lire » n'est pas « aucun contrat », meme argument que juste
    # au-dessus.
    def _strike_lisible(c):
        try:
            return math.isfinite(float(c.get("strike_price")))
        except (TypeError, ValueError):
            return False

    lisibles = [c for c in contracts if _strike_lisible(c)]
    if not lisibles:
        raise AlpacaCLIError(
            "received %d option contract(s) for %s but could not read a "
            "numeric strike_price on any of them. Refusing to pick one at "
            "random -- with an unreadable strike, 'closest to spot' is decided "
            "by list order, not by distance." % (len(contracts), underlying))
    if len(lisibles) != len(contracts):
        print("  WARNING: %d of %d option contracts for %s had an unreadable "
              "strike_price and were skipped."
              % (len(contracts) - len(lisibles), len(contracts), underlying),
              flush=True)
    contracts = lisibles

    # LA FENETRE D'ECHEANCE ETAIT DEMANDEE, JAMAIS VERIFIEE. Ajoute le
    # 30/08/2026. `expiration_date_gte/lte` part dans la requete, et le
    # contrat rendu etait achete sans qu'on regarde SA date. C'est le motif
    # que cette fonction meme a deja corrige DEUX fois -- la troncature de
    # page le 24/08, l'ordre a echeance egale le 27/08 : faire confiance a ce
    # qu'une reponse externe est censee contenir plutot que de le mesurer.
    #
    # « 7 a 21 jours » n'est pas un detail : c'est publie dans le README, le
    # deck, le script video et la fiche de soumission, et c'est ce que le
    # payoff simule par backtest.py suppose. Un contrat a six mois passerait
    # ces trois affirmations a faux sans qu'une ligne ne bronche.
    #
    # Mesure du 30/08 contre l'API reelle, SPY, put, fenetre 06/09-20/09 :
    # 100 contrats rendus, echeances 08/09 et 09/09, ZERO hors fenetre. Ce
    # filtre est donc sans effet aujourd'hui -- c'est un trou de detection
    # qu'il ferme, pas une panne observee.
    dans_la_fenetre = [c for c in contracts
                       if gte <= str(c.get("expiration_date", "")) <= lte]
    if len(dans_la_fenetre) != len(contracts):
        print("  WARNING: %d of %d option contracts for %s came back OUTSIDE "
              "the %d-%d day window that was asked for, and were dropped. The "
              "query filters on expiration_date; something answered it "
              "differently."
              % (len(contracts) - len(dans_la_fenetre), len(contracts),
                 underlying, min_days_out, max_days_out), flush=True)
    if not dans_la_fenetre:
        # Meme discipline que les strikes illisibles juste au-dessus : on ne
        # choisit pas au hasard parmi des contrats dont aucun ne repond a la
        # question posee. Le symbole saute sa journee, et le message dit
        # pourquoi.
        print("  WARNING: not one of the %d option contracts returned for %s "
              "falls inside the %d-%d day window. No contract picked."
              % (len(contracts), underlying, min_days_out, max_days_out),
              flush=True)
        return None
    contracts = dans_la_fenetre

    # AJOUTE le 27/08/2026. La bande a +/-5% (ci-dessus, 24/08) a REDUIT la
    # troncature de page sans la fermer, et l'arithmetique le montre :
    #
    #   bande +/-5% sur SPY a 762.98 = 76 points de strikes
    #   76 strikes x 6 echeances (lun/mer/ven sur 7-21 jours) = 462 contrats
    #   tronque a 100, tri par strike CROISSANT -> la page s'arrete vers 740,
    #   et le spot n'y est PAS
    #
    # Reproduit sur une page ainsi construite : la fonction rendait un contrat
    # 22 points DANS LA MONNAIE (~2215 $ d'intrinseque) presente comme le plus
    # proche de la monnaie, sans un mot. C'est la panne exacte du 24/08, par le
    # meme mecanisme, a une echelle plus fine.
    #
    # PORTEE HONNETE : je n'ai pas pu verifier contre l'API reelle si SPY a
    # effectivement des strikes au dollar et six echeances dans cette fenetre.
    # Ceci ne prouve donc pas que le cas etait actif -- ca ferme un trou de
    # detection pour une panne deja subie une fois.
    #
    # Le test est en DEUX parties, et la seconde evite un refus permanent :
    # une page PLEINE peut parfaitement encadrer le spot (peu d'echeances,
    # strikes serres), et le tri par strike garantit alors que le plus proche
    # y est. On ne refuse que si la page est pleine ET n'atteint pas le spot.
    # Une page COURTE n'a pas ete tronquee : si aucun strike n'atteint le spot,
    # c'est le marche qui est ainsi, et le plus proche est vraiment le plus
    # proche.
    if len(contracts) >= CONTRACTS_PAGE_LIMIT:
        strikes = [float(c["strike_price"]) for c in contracts
                   if c.get("strike_price") is not None]
        if strikes and not (min(strikes) <= spot <= max(strikes)):
            print(
                "  WARNING: /v2/options/contracts a rendu %d resultats (la page "
                "entiere) pour %s, strikes %.2f a %.2f, alors que le spot est a "
                "%.2f. La reponse est triee par strike CROISSANT : elle a donc "
                "ete TRONQUEE avant d'atteindre la monnaie, et « le plus proche "
                "du spot » ne veut plus rien dire sur cet echantillon. Aucun "
                "contrat retenu. Corriger en resserrant STRIKE_BAND_PCT (%.2f "
                "aujourd'hui) ou en reduisant la fenetre d'echeances (%d-%d "
                "jours)."
                % (len(contracts), underlying, min(strikes), max(strikes), spot,
                   STRIKE_BAND_PCT, min_days_out, max_days_out)
            )
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


# Statuts d'ordre qui veulent dire « rien ne s'est passe ». Constante PARTAGEE
# entre la soumission et la cloture -- ecrire cette liste deux fois serait la
# faire diverger, ce qui s'est produit deux fois dans ce depot le meme jour
# (reconnaissance des options, verdict binaire des rapports).
ECHECS_TERMINAUX = {"rejected", "canceled", "cancelled", "expired", "suspended"}


def close_position(symbol: str) -> Any:
    """VERIFIED 24/08 against CLI v0.0.13 by actually closing a live paper
    position: the flag is --symbol-or-asset-id, NOT --symbol. The wrong form
    exits 1 with {"error": "unknown flag: --symbol"}, which run() turns into
    an AlpacaCLIError -- meaning manage_exits() would have raised every time
    a take-profit or stop-loss actually fired. This is the one branch mocks
    could never catch, and it sat in the risk system, not a nice-to-have."""
    resultat = run(["position", "close", "--symbol-or-asset-id", symbol])

    # AJOUTE le 27/08/2026, miroir du controle de statut pose sur la
    # SOUMISSION quelques minutes plus tot. Ici le resultat etait purement et
    # simplement JETE, et manage_exits enchaine sur un commentaire qui dit
    # « the position IS closed at this point » -- une hypothese, pas une
    # verification.
    #
    # Consequence si Alpaca rend un ordre de cloture au statut « rejected »
    # (permission options revoquee, position deja fermee ailleurs, contrat
    # suspendu) : la position est comptee comme FERMEE, le compteur de pertes
    # consecutives s'incremente, le tableau de bord affiche un badge VERT
    # « position closed » -- et la position reste OUVERTE, au-dela de son
    # stop-loss, sans surveillance particuliere.
    #
    # C'est exactement la panne que tout ce sous-systeme existe pour empecher,
    # et c'est le cote le plus grave des deux : une entree ratee coute une
    # occasion, une SORTIE ratee laisse une perte courir.
    #
    # run() leve deja sur un code de retour non nul et sur un corps d'erreur ;
    # le trou est l'appel qui REUSSIT en rendant un ordre au statut d'echec.
    # En levant ici, manage_exits rattrape et produit un ExitKind.ERROR, donc
    # le badge rouge « close FAILED - position still open ».
    if isinstance(resultat, dict):
        statut = str(resultat.get("status", "")).lower()
        if statut in ECHECS_TERMINAUX:
            motif = (resultat.get("reason") or resultat.get("reject_reason")
                     or resultat.get("message") or "no reason given")
            raise AlpacaCLIError(
                "the close order for %s came back with status '%s' (%s). The "
                "position is very likely STILL OPEN. Reporting this as a "
                "failed close rather than a completed one, so it is not "
                "counted as a realised loss and the dashboard does not show a "
                "position that never closed." % (symbol, statut, motif))
    return resultat


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

    # AJOUTE le 27/08/2026, la veille du kickoff. Cette fonction ne regardait
    # que la PRESENCE d'un id. Or l'objet ordre d'Alpaca porte TOUJOURS un
    # `status`, et « rejected » en fait partie. Mesure avant correctif :
    #
    #     accepted / filled   -> id rendu   (juste)
    #     REJECTED            -> id rendu   -> badge VERT « traded »
    #     canceled / expired  -> id rendu   -> badge VERT « traded »
    #
    # Un ordre REJETE produisait donc, sur la page publique, la meme preuve
    # verte qu'un ordre execute. Trois consequences, aucune cosmetique :
    #   . le tableau de bord affirme un trade qui n'a pas eu lieu ;
    #   . record_order_submitted() arme le garde anti-doublon, donc ce symbole
    #     ne peut plus etre retente de la journee ;
    #   . l'exposition compte une prime jamais depensee, ce qui retrecit le
    #     budget restant pour les autres symboles.
    #
    # Ce n'est pas un cas d'ecole : le journal d'ingenierie releve un fil de
    # forum Alpaca du 30 juillet 2026 ou des comptes paper perdent l'acces aux
    # options du jour au lendemain. « options trading not enabled » est le
    # motif de rejet le plus plausible de la semaine.
    #
    # On ne refuse QUE les statuts terminaux d'echec. Un ordre de marche est
    # rarement « filled » a la milliseconde ou l'API repond : exiger « filled »
    # bloquerait la totalite des trades.
    statut = str(result.get("status", "")).lower()
    if statut in ECHECS_TERMINAUX:
        motif = (result.get("reason") or result.get("reject_reason")
                 or result.get("message") or "no reason given")
        raise AlpacaCLIError(
            "order for %s was accepted by the CLI but came back with status "
            "'%s' (%s). No position was opened. Reporting this as a failure "
            "rather than a submitted order, so the dashboard does not show a "
            "trade that never happened and the duplicate-order guard stays "
            "unarmed for a retry." % (option_symbol, statut, motif))

    # Un statut ABSENT n'est PAS traite comme un echec, et c'est un choix :
    # « on ne sait pas » n'est pas « ca a rate », et l'ordre a pu partir. Lever
    # ici laisserait le garde anti-doublon desarme sur un ordre peut-etre reel.
    # Meme raisonnement que le delai depasse, corrige le matin meme.
    if not statut:
        print("  WARNING: the order response for %s carried no 'status' field, "
              "so whether it was accepted is UNKNOWN. Treating it as submitted "
              "(the safe direction: the duplicate-order guard gets armed), but "
              "verify with Alpaca before assuming a position exists."
              % option_symbol, flush=True)

    return result["id"]
