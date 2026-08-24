"""Builds docs/data.json — the snapshot the hosted dashboard (docs/index.html)
reads. Run this after (or as part of) each agent.py run.

Hosting choice: GitHub Pages serving the docs/ folder of this same public
repo, not a separate server. Two reasons: it reuses a pattern Spap already
has running for another project's dashboard (SNIPER's D31/precision_vote.py
on GitHub Pages), and — more importantly — it means the API secret keys
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

DOCS_DIR = Path(__file__).parent / "docs"
DATA_FILE = DOCS_DIR / "data.json"


def build_snapshot() -> dict:
    config.require_credentials()
    account = alpaca_cli.get_account()
    positions = alpaca_cli.list_positions()
    recent = decision_log.read_log(limit=30)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "team": "Hindsight Alpha",
        "account": {
            "id": account.get("id"),
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
        "positions": positions,
        "recent_decisions": recent,
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
        with open(tmp, "w") as fh:
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


def git_publish() -> None:
    subprocess.run(["git", "add", "docs/data.json", "decision_log.jsonl"], check=True)
    result = subprocess.run(["git", "diff", "--cached", "--quiet"])
    if result.returncode == 0:
        print("Nothing changed since last publish — skipping commit.")
        return
    subprocess.run(
        ["git", "commit", "-m", f"dashboard: snapshot {datetime.now(timezone.utc).isoformat()}"],
        check=True,
    )
    subprocess.run(["git", "push"], check=True)


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
