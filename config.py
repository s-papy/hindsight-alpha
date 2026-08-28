# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha
#
# Sous licence MIT, redistribuer ce fichier -- entier ou par morceaux --
# OBLIGE a conserver cet avis. C'est la seule contrainte de la licence, et
# c'est la raison d'etre de ces trois lignes : un fichier copie-colle
# emporte desormais sa provenance avec lui.

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

# Photographie de l'environnement AVANT tout chargement de fichier : c'est
# la seule facon de savoir ensuite qui a eu la priorite.
_ENVIRONNEMENT_AVANT = dict(os.environ)

def _signaler_precedence(chemin) -> list:
    """Une variable presente A LA FOIS dans l'environnement et dans le fichier,
    avec des valeurs DIFFERENTES ?

    AJOUTE le 27/08/2026. Mesure sur la bibliotheque elle-meme : load_dotenv()
    n'ECRASE PAS, par defaut, une variable deja presente dans l'environnement.

        environnement pre-rempli + fichier charge -> valeur de L'ENVIRONNEMENT
        avec override=True                        -> valeur du FICHIER

    Consequence, et elle tombe pile le jour du kickoff : si un identifiant
    traine dans le shell (un `export` dans un profil, un `launchctl setenv`)
    et que l'operateur bascule le fichier sur le compte du hackathon, l'agent
    continue silencieusement sur l'ANCIEN compte. Rien ne le dit -- pas meme
    la detection de bascule de compte de risk_gates, qui remarque un
    changement, pas son ABSENCE quand on en attendait un.

    LA PRECEDENCE N'EST PAS CHANGEE, deliberement : forcer override=True
    surprendrait dans l'autre sens, en ignorant un reglage volontaire passe
    par l'environnement (CI, essai ponctuel). Les deux comportements peuvent
    etre justes ; ce qui ne l'est pas, c'est de choisir en silence.

    Les VALEURS ne sont jamais imprimees -- seulement les NOMS. Un
    avertissement qui divulgue ce qu'il protege serait pire que son absence."""
    try:
        from dotenv import dotenv_values
    except ImportError:
        return []
    try:
        du_fichier = dotenv_values(chemin)
    except OSError:
        return []
    divergentes = [
        nom for nom, valeur in du_fichier.items()
        if valeur is not None
        and nom in _ENVIRONNEMENT_AVANT
        and _ENVIRONNEMENT_AVANT[nom] != valeur
    ]
    if divergentes:
        print(
            "  WARNING: %s est(sont) defini(s) A LA FOIS dans l'environnement "
            "et dans le fichier de configuration, avec des valeurs "
            "DIFFERENTES. python-dotenv n'ecrase pas : c'est la valeur de "
            "L'ENVIRONNEMENT qui est utilisee, celle du fichier est ignoree. "
            "Si tu viens de basculer de compte, la bascule N'A PAS pris "
            "effet -- `unset %s` puis relance."
            % (", ".join(divergentes), " ".join(divergentes)),
            file=sys.stderr, flush=True)
    return divergentes

try:
    from dotenv import load_dotenv
    _CHEMIN_CONFIG = Path(__file__).parent / ".env"
    load_dotenv(_CHEMIN_CONFIG)
    _signaler_precedence(_CHEMIN_CONFIG)
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


def raison_de_refus_du_compte(account: dict) -> "str | None":
    """La regle de verification du compte, ecrite UNE fois.

    Rend None si l'on peut agir (compte conforme, ou aucun compte declare),
    sinon la raison du refus -- a prefixer par l'appelant selon ce qu'il
    refuse d'ailleurs (« no new entry », « refused to close », « refusing to
    publish »).

    EXTRAITE le 28/08/2026, le jour meme ou elle a ete ecrite TROIS fois :
    dans check_gates (entrees), manage_exits (sorties) et build_snapshot
    (publication). Le depot enseigne pourtant, noir sur blanc et deux fois
    ailleurs, qu'« une regle ecrite deux fois n'est vraie qu'a un seul
    endroit ». Je l'ai cite en ecrivant la premiere, puis je l'ai enfreint
    dans l'heure.

    Et elles avaient DEJA diverge, avant meme d'etre relues -- trois
    normalisations differentes du numero lu :

        check_gates        str(reel).strip() if reel is not None else ""
        manage_exits       str(... or "").strip()
        build_snapshot     str(... or "").strip()

    La premiere rendrait "0" la ou les deux autres rendent "" : sans
    consequence sur un vrai numero Alpaca, mais c'est exactement ainsi que
    deux copies commencent a repondre differemment.

    TROIS etats, jamais deux -- c'est le coeur de la regle :
      . declare et DIFFERENT  -> refus ;
      . declare et ILLISIBLE  -> refus aussi : ne pas pouvoir prouver sur
        quel compte on est n'est pas « c'est le bon » ;
      . rien de declare       -> None. Rien a comparer n'est pas une faute,
        sinon un dossier sans ALPACA_ACCOUNT_ID serait paralyse. L'appelant
        avertit.
    """
    attendu = ACCOUNT_ID
    if not attendu:
        return None
    brut = account.get("account_number")
    reel = "" if brut is None else str(brut).strip()
    if not reel:
        return ("the account response carried no account_number, so this run "
                "cannot prove which account it is on (declared: %r)"
                % (str(attendu).strip(),))
    if reel != str(attendu).strip():
        return ("this run is on account %r but the configuration declares %r"
                % (reel, str(attendu).strip()))
    return None


def compte_est_declare() -> bool:
    """Y a-t-il un compte attendu ? Sert aux appelants a decider s'ils
    avertissent (rien a comparer) ou se taisent."""
    return bool(ACCOUNT_ID)


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
