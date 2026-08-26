"""Loads Alpaca paper-trading credentials from .env. Never commit .env.

Used by alpaca_cli.py (the subprocess wrapper around Alpaca's official CLI).
The `alpaca` CLI itself only reads ALPACA_API_KEY / ALPACA_SECRET_KEY /
ALPACA_LIVE_TRADE from the environment — there is no base-url variable for
it, paper trading is simply its default when ALPACA_LIVE_TRADE isn't set to
true. BASE_URL is kept here only for reference/logging, not passed to the CLI.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # fall back to real environment variables if python-dotenv isn't installed

API_KEY = os.environ.get("ALPACA_API_KEY")
SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY")
BASE_URL = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets/v2")
ACCOUNT_ID = os.environ.get("ALPACA_ACCOUNT_ID")

_LIVE_FLAG = os.environ.get("ALPACA_LIVE_TRADE", "").strip().lower()

# CORRIGE 26/08. C'etait une liste de valeurs VRAIES:
#     PAPER = _LIVE_FLAG not in ("true", "1", "yes")
# Mesure: `on`, `y`, `t`, `2`, `enabled` passaient donc pour du paper.
#
# Ce n'etait PAS un risque de trading reel, et il faut le dire precisement: les
# deux seuls appels au CLI passent par cli_env(), qui RETIRE la variable de
# l'environnement du sous-processus. Le CLI ne peut donc jamais la voir, quelle
# que soit sa graphie. La protection tenait.
#
# Le trou etait dans le DIAGNOSTIC, pas dans la garde. Un operateur qui ecrit
# ALPACA_LIVE_TRADE=on en croyant activer le live etait silencieusement ignore:
# l'agent tradait en paper sans dire un mot. Pour un projet dont la these est
# d'etre explicite sur ce qu'il fait, se taire dans ce cas est le mauvais
# comportement -- meme quand le resultat est sur.
#
# On enumere donc les valeurs FAUSSES, et tout le reste fait refuser de
# demarrer: une valeur qu'on ne sait pas interpreter n'est pas une permission
# de supposer. Ne rien mettre reste le cas normal et silencieux.
_VALEURS_FAUSSES = ("", "false", "0", "no", "off", "n", "f")
PAPER = _LIVE_FLAG in _VALEURS_FAUSSES


def require_credentials() -> None:
    if not API_KEY or not SECRET_KEY:
        sys.exit(
            "Missing ALPACA_API_KEY / ALPACA_SECRET_KEY.\n"
            "Create a .env file next to this script (see .env.example) with your "
            "Alpaca PAPER trading keys, generated from the Alpaca dashboard."
        )
    if not PAPER:
        sys.exit(
            f"ALPACA_LIVE_TRADE is set to {_LIVE_FLAG!r} in this environment.\n"
            "This agent is built and tested for paper trading only — refusing to run "
            "against anything that isn't an explicit, recognised falsy value "
            f"({', '.join(repr(v) for v in _VALEURS_FAUSSES if v)}, or unset)."
        )


def cli_env() -> dict:
    """Environment dict for subprocess calls to the `alpaca` CLI: inherits the
    current process environment but forces ALPACA_LIVE_TRADE unset, regardless
    of what might already be set on the machine — paper is the CLI's default
    only in the *absence* of that variable, so absence is enforced here rather
    than assumed."""
    env = os.environ.copy()
    env["ALPACA_API_KEY"] = API_KEY or ""
    env["ALPACA_SECRET_KEY"] = SECRET_KEY or ""
    env.pop("ALPACA_LIVE_TRADE", None)
    return env
