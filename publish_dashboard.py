# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Spap - Hindsight Alpha
# Source: https://github.com/s-papy/hindsight-alpha
#
# Sous licence MIT, redistribuer ce fichier -- entier ou par morceaux --
# OBLIGE a conserver cet avis. C'est la seule contrainte de la licence, et
# c'est la raison d'etre de ces trois lignes : un fichier copie-colle
# emporte desormais sa provenance avec lui.

"""Builds docs/data.json — the snapshot the hosted dashboard (docs/index.html)
reads. Run this after (or as part of) each agent.py run.

Hosting choice: GitHub Pages serving the docs/ folder of this same public
repo, not a separate server. Two reasons: it reuses a dashboard pattern
already proven on an earlier project, and — more importantly — it means the API secret keys
never have to live anywhere except this machine's .env. A hosted server
approach would need the keys wherever it runs; a static page instead just
needs a JSON snapshot regenerated locally, committed, and pushed. The public
page never talks to Alpaca directly and never sees a key.

Usage:
    python publish_dashboard.py             # writes docs/data.json only
    python publish_dashboard.py --git-push   # also git add/commit/push

--git-push is opt-in and separate on purpose: writing the file is safe to
run unattended every day, but pushing to the public repo is a step this
project's own rules say needs an explicit decision each time, not a silent
default in a script.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import alpaca_cli
import config
import decision_log
from monitor_exits import MONITOR_STATUS_FILE

DOCS_DIR = Path(__file__).parent / "docs"
DATA_FILE = DOCS_DIR / "data.json"


def _read_monitor_status() -> dict | None:
    """Best-effort read of monitor_exits.py's every-run status marker (see
    MONITOR_STATUS_FILE's own comment in monitor_exits.py for why this exists
    separately from decision_log.jsonl: found 25/08, by checking the dashboard
    health banner against a real incident, that decision_log.jsonl alone
    can't tell a reader whether the monitor is CURRENTLY healthy -- only
    whether it was ever interesting -- because a routine successful check is
    never logged there. Missing or corrupt file -> None, same non-blocking
    default as every other best-effort read in this project (e.g. a bad
    decision_log line just gets skipped, not fatal): a stale/missing status
    file should degrade the dashboard's health banner to 'no data', never
    break the whole snapshot build."""
    try:
        return json.loads(MONITOR_STATUS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# AJOUTE le 27/08/2026. Le commentaire de `account` ci-dessous enonce le
# principe -- « le payload d'Alpaca est recopie ici, et il grandira » -- et
# c'est pour cela que `account` a ete reduit a six champs choisis. `positions`,
# une ligne plus bas, recopiait pourtant le payload ENTIER.
#
# Mesure sur la position reellement ouverte, chacun des 19 champs publies
# croise contre docs/index.html ET test_dashboard.py :
#
#   consommes (7)  asset_class, cost_basis, qty, side, symbol,
#                  unrealized_pl, unrealized_plpc
#   personne (12)  asset_id, asset_marginable, avg_entry_price, change_today,
#                  current_price, exchange, lastday_price, market_value,
#                  qty_available, unrealized_intraday_pl,
#                  unrealized_intraday_plpc, usd
#
# `asset_id` est un UUID interne : exactement la nature du champ retire de
# `account` le meme jour, pour exactement ce motif. Le probleme n'est pas
# qu'un de ces champs soit dangereux -- aucun n'autorise quoi que ce soit
# sans les cles -- c'est que DOUZE champs partaient sans que personne ne
# l'ait decide, dans un fichier suivi par git et servi publiquement.
#
# La liste ci-dessous est donc une DECISION, pas un reste. Y ajouter un champ
# doit rester un acte volontaire : un test refuse tout champ publie que la
# page n'utilise pas.
CHAMPS_DE_POSITION_PUBLIES = (
    "symbol", "qty", "side", "asset_class",
    "cost_basis", "unrealized_pl", "unrealized_plpc",
)


def _position_publiable(position: dict) -> dict:
    """Ne publie que les champs que la page affiche reellement.

    `.get()` plutot qu'une indexation : un champ absent du payload devient
    None, ce que la page sait deja rendre. L'inverse -- lever ici -- ferait
    echouer toute la publication a cause d'un seul champ manquant sur une
    seule position, alors que ce fichier n'a qu'un role d'affichage.
    """
    return {champ: position.get(champ) for champ in CHAMPS_DE_POSITION_PUBLIES}


def build_snapshot() -> dict:
    config.require_credentials()
    account = alpaca_cli.get_account()

    # AJOUTE le 28/08/2026, en completant le garde de compte pose le meme
    # matin dans check_gates (entrees) puis manage_exits (sorties). Ce
    # fichier-ci est le troisieme acteur, et c'est celui qu'un JUGE regarde :
    # il publie `account_number`, les positions et l'equite sur une page
    # publique, toutes les 30 minutes, sans personne devant.
    #
    # Sur un mauvais compte, il republiait donc en silence le numero, les
    # positions et l'equite d'un AUTRE compte -- ecrasant la preuve du
    # hackathon. Un juge qui compare le numero declare dans la soumission a
    # celui affiche sur la page verrait un desaccord sans explication, sur la
    # seule chose que ce projet lui demande de croire.
    #
    # On LEVE plutot que de publier. La page porte deja une banniere qui
    # vieillit et qui dit « snapshot from X ago » : une page perimee est
    # honnete, une page qui affirme le mauvais compte ne l'est pas. Sous
    # launchd, l'echec part dans le log declare par le plist.
    refus = config.raison_de_refus_du_compte(account)
    if refus:
        raise RuntimeError(
            "refusing to publish: %s. Publishing would overwrite the public "
            "dashboard with another account's positions and equity." % refus)
    if not config.compte_est_declare():
        print("  WARNING: no ALPACA_ACCOUNT_ID declared -- this snapshot is "
              "published without any check that it describes the intended "
              "account.", flush=True)

    positions = alpaca_cli.list_positions()
    recent = decision_log.read_log(limit=30)
    monitor_status = _read_monitor_status()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "team": "Hindsight Alpha",
        # Provenance embarquee dans les DONNEES, pas seulement dans la
        # page : si quelqu'un reprend data.json sans le HTML, l'origine
        # part avec. Trois champs statiques, aucun pistage.
        "source": "https://github.com/s-papy/hindsight-alpha",
        "author": "Spap",
        "license": "MIT",
        "account": {
            # RETIRE le 27/08 : "id": account.get("id") -- l'UUID INTERNE du
            # compte, 36 caracteres. Trouve en croisant ce que ce fichier
            # publie avec ce que docs/index.html lit : la page ne s'en sert
            # QUE comme repli derriere account_number, toujours present sur un
            # compte reel. Il n'etait donc affiche a personne, jamais, et
            # partait pourtant dans un fichier suivi par git et servi
            # publiquement par GitHub Pages a chaque publication.
            #
            # Il etait deja dans 6 commits pousses au moment de la
            # decouverte. Rien ne l'en retire sans reecrire l'historique, ce
            # que ce projet s'interdit : ce correctif arrete la suite, pas le
            # passe. Ni cet UUID ni le numero de compte n'autorisent quoi que
            # ce soit sans les cles -- ce sont des identifiants, pas des
            # pouvoirs. Ce qui compte, c'est qu'un champ soit parti sans que
            # personne ne l'ait decide : le payload d'Alpaca est recopie ici,
            # et il grandira.
            #
            # risk_gates.py continue d'utiliser account["id"] pour detecter
            # une bascule de compte -- usage INTERNE, jamais publie.
            #
            # account_number ("PA..." on paper accounts) is the human-visible
            # identifier -- what the hackathon submission form's "Alpaca
            # account ID" field almost certainly means, per Alpaca's own docs
            # distinguishing it from the internal UUID `id`. Surfaced
            # separately so the dashboard shows the SAME identifier that's
            # declared in the submission, not just the UUID -- a mismatch
            # here would make the "does this dashboard match the submitted
            # account" cross-check (the whole reason the dashboard shows an
            # account ID at all) confusing instead of reassuring.
            "account_number": account.get("account_number"),
            "status": account.get("status"),
            "equity": account.get("equity"),
            "cash": account.get("cash"),
            "buying_power": account.get("buying_power"),
            "portfolio_value": account.get("portfolio_value"),
        },
        "positions": [_position_publiable(p) for p in positions],
        "recent_decisions": recent,
        "monitor_status": monitor_status,
    }


def write_snapshot() -> Path:
    DOCS_DIR.mkdir(exist_ok=True)
    snapshot = build_snapshot()
    # Atomic write -- flagged but deliberately left alone in a "cherche
    # encore" pass earlier the same day ("same shape as state.json's [fixed]
    # torn-write bug, but exposure is lower: this script isn't scheduled,
    # write and commit happen in the same process, and the next run
    # overwrites the file"). Revisited and fixed on request: that reasoning
    # was about how LIKELY a torn write is here, not about the CONSEQUENCE
    # if one happens, and the consequence is real -- unlike state.json,
    # which is code this project runs, docs/data.json is content a judge's
    # browser parses with JSON.parse(). Path.write_text() opens in mode "w",
    # which truncates to 0 bytes before writing a single byte of the new
    # content (probed directly on this exact file, same mechanism as the
    # state.json bug: 40 bytes -> 0 the instant the file is opened) -- a
    # process killed mid-write (or a --git-push mid-commit interrupted the
    # same way) would leave docs/data.json invalid, and GitHub Pages would
    # serve that broken file to every visitor, including a judge, until the
    # next successful run overwrites it. Same fix as _save_state() in
    # risk_gates.py: write to a temp file in the same directory, fsync, then
    # os.replace() -- atomic on POSIX, so a reader always sees either the
    # complete old snapshot or the complete new one, never a half-written
    # file.
    tmp = DATA_FILE.with_name(DATA_FILE.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(snapshot, indent=2))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, DATA_FILE)
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise
    return DATA_FILE


# AJOUTE le 27/08/2026, le jour ou les LaunchAgents ont ete charges -- donc
# sur du code qui tourne desormais SANS PERSONNE DEVANT, toutes les 30 minutes.
#
# Sous launchd il n'y a AUCUN terminal. Si git decide de demander quoi que ce
# soit -- identifiants expires, trousseau verrouille, empreinte d'hote changee --
# il attend une reponse qui ne viendra jamais. GIT_TERMINAL_PROMPT=0 le fait
# ECHOUER au lieu d'attendre, et GIT_ASKPASS pointe vers un programme qui rend
# toujours faux pour fermer le second chemin (celui des helpers graphiques).
#
# Mieux vaut un echec net dans le log qu'un processus fige : launchd ne demarre
# pas une seconde instance tant que la premiere tourne, donc une seule attente
# infinie arrete la publication POUR DE BON.
_ENV_GIT = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="/usr/bin/false")

# Les operations locales sont rapides ; seul le reseau merite d'attendre.
_DELAI_LOCAL = 30
_DELAI_RESEAU = 120


def git_publish() -> None:
    paths = ["docs/data.json", "decision_log.jsonl"]
    subprocess.run(["git", "add", *paths], check=True,
                   timeout=_DELAI_LOCAL, env=_ENV_GIT)
    # Both calls below are scoped to `paths` on purpose -- found 24/08,
    # a review pass. `git diff --cached --quiet` with NO pathspec checks
    # the whole index, not just the two files just staged above: if anything
    # else happened to already be staged in this working tree at this exact
    # moment (a terminal session mid multi-file review, say -- this repo's
    # own workflow runs plenty of ad hoc `git add` before this function is
    # ever called), that unrelated staged diff makes this "did anything
    # change" check report true even when docs/data.json and
    # decision_log.jsonl are byte-identical to HEAD. And an unscoped `git
    # commit` would then scoop that unrelated staged file into a commit
    # whose message claims to be only "dashboard: snapshot ...", pushing it
    # to the public repo under a misleading label -- a commit lying about
    # its own contents is exactly the kind of untrustworthy trace this
    # project exists to catch elsewhere. Reproduced in a throwaway repo:
    # staged an unrelated file, left the dashboard files unchanged, and
    # confirmed the unscoped diff reported "changed" anyway (exit 1); the
    # scoped `-- <pathspec>` form correctly reported "unchanged" (exit 0) in
    # the same state, and `git commit -m ... -- <pathspec>` committed only
    # the intended files while leaving the unrelated staged file untouched
    # and still staged for whoever put it there.
    result = subprocess.run(["git", "diff", "--cached", "--quiet", "--", *paths],
                            timeout=_DELAI_LOCAL, env=_ENV_GIT)
    if result.returncode == 0:
        print("Nothing changed since last publish — skipping commit.")
        return
    # AJOUTE le 27/08/2026 au soir, apres avoir lu publish_dashboard.log en
    # vrai : le hook de pre-commit lance garde_fou.py a CHAQUE publication,
    # toutes les 30 minutes, et le log en porte la trace complete.
    #
    # Le couplage qui en decoule : si le verdict passe au 🔴 -- un chiffre de
    # livrable qui derive, un faux positif d'un controle, un plist casse --
    # `git commit` est REFUSE, CalledProcessError remonte, et ce script meurt.
    # Toutes les 30 minutes. Le tableau de bord public gele pendant la semaine
    # ou des juges le regardent.
    #
    # Mesure avant ce correctif : l'exception remontait SANS UN MOT, sur une
    # trace brute, dans un fichier de log gitignore que personne ne lit.
    #
    # La banniere de la page finit par dire « snapshot from X ago » (chemin
    # verifie le 26/08), donc le silence devient visible. Sa CAUSE, non -- et
    # c'est elle qui permet d'agir. On la nomme, et on releve : un commit
    # refuse reste une ERREUR, sans quoi launchd croirait a une publication
    # reussie.
    try:
        subprocess.run(
            ["git", "commit", "-m", f"dashboard: snapshot {datetime.now(timezone.utc).isoformat()}", "--", *paths],
            check=True, timeout=_DELAI_LOCAL, env=_ENV_GIT,
        )
    except subprocess.CalledProcessError as refus:
        print(
            "  ERROR: `git commit` was refused (exit %d). The most likely "
            "cause is this repo's own pre-commit hook, which runs "
            "garde_fou.py and refuses the commit on a red verdict. While that "
            "verdict stands, EVERY publish attempt fails the same way and the "
            "public dashboard stops updating -- its banner will start "
            "reporting a stale snapshot, without saying why. Run "
            "`python3 garde_fou.py` to see what it is refusing."
            % refus.returncode,
            flush=True,
        )
        raise

    # Le push, et le seul appel qui parle au reseau. Sa panne se raconte comme
    # celle de l'ordre qui expire dans agent.py, corrigee le matin meme : un
    # delai depasse ne veut pas dire « ca a echoue », il veut dire « ON NE SAIT
    # PAS ». Le commit local est deja fait ; le push a pu atteindre GitHub sans
    # rendre la main. Le dire, plutot que de laisser croire a un echec net.
    try:
        subprocess.run(["git", "push"], check=True,
                       timeout=_DELAI_RESEAU, env=_ENV_GIT)
    except subprocess.TimeoutExpired:
        print("  WARNING: `git push` did not answer within %ds. The commit is "
              "already made LOCALLY, and the push MAY OR MAY NOT have reached "
              "GitHub -- this is UNKNOWN, not a failure. Run `git push` by hand "
              "and check the repo before assuming the dashboard is stale."
              % _DELAI_RESEAU, flush=True)
        return


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--git-push", action="store_true", help="also commit and push docs/data.json")
    args = parser.parse_args()

    path = write_snapshot()
    print(f"Wrote {path}")

    if args.git_push:
        git_publish()
        print("Published to GitHub Pages (after the next Pages build completes).")


if __name__ == "__main__":
    main()
