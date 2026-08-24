"""Append-only log of every agent run's decisions — one JSON object per line
in decision_log.jsonl. This is what the hosted dashboard reads to show a
history, not just today's snapshot, and it's also the raw material for the
one-page write-up and the demo video ("here's what it decided and why,
every day this week").

Not gitignored deliberately — unlike state.json (private run-state) this
log is meant to be committed and published, it's evidence of the agent's
reasoning over the week, not a secret.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

LOG_FILE = Path(__file__).parent / "decision_log.jsonl"


def log_run(record: Dict[str, Any]) -> None:
    """Appends one record. Always stamps a UTC timestamp; caller supplies
    the rest (market_open, exits, symbol verdicts, trade decision, error)."""
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), **record}
    with LOG_FILE.open("a") as f:
        f.write(json.dumps(record) + "\n")


def log_run_or_dump(record: Dict[str, Any], context: str = "") -> bool:
    """log_run(), but never raises at the caller. Returns True if the record
    reached the file, False if it had to be dumped to stdout instead.

    Moved here 24/08 from two near-identical copies in agent.py's and
    monitor_exits.py's `finally` blocks -- they had already diverged in
    wording on their first edit, which is the copy-paste-then-tweak
    signature. This module is the right home because it already owns the
    READ side of exactly this policy: read_log() warns and skips a corrupt
    line rather than aborting its caller. Owning the write side too makes
    the module's guarantee symmetric and stated once -- decision_log never
    takes down its callers, in either direction -- instead of a contract
    enforced from outside by every caller remembering to.

    Dumping to stdout on failure means the trace survives wherever stdout
    goes (launchd's log, a terminal) rather than nowhere. flush=True because
    the situations that break the append (full disk, killed process) are
    exactly the ones where a buffered dump never lands."""
    try:
        log_run(record)
        return True
    except Exception as log_error:
        print(
            f"WARNING: could not write to {LOG_FILE.name} "
            f"({type(log_error).__name__}: {log_error}). "
            + (context + " " if context else "")
            + "Dumping the record here so it is not lost:",
            flush=True,
        )
        print(json.dumps(record, indent=2, default=str), flush=True)
        return False


def read_log(limit: int = 30) -> List[Dict[str, Any]]:
    """Most recent `limit` records, newest first. Empty list if no log yet.

    Skips (with a warning) any line that fails to parse as JSON, rather
    than raising and aborting the whole read. Found 24/08, "cherche
    encore": log_run() below writes with a single f.write() call, but
    that's still two syscall-level steps (write the bytes, then the OS
    flushes/closes) -- a process kill or a crash at exactly the wrong
    moment (e.g. right after agent.py submits a paper order, one of the
    crash windows this same session's idempotency guard was written to
    survive) can leave a truncated, unparseable final line in
    decision_log.jsonl. Before this fix, ONE bad line here would raise
    json.JSONDecodeError out of read_log(), which publish_dashboard.py
    calls directly and unguarded -- taking down every future dashboard
    build, not just losing that one entry, until someone manually finds
    and fixes the bad line. Same "one bad record shouldn't take down
    everything else" principle this project already applies elsewhere
    (evaluate_symbol's per-symbol isolation, the entry loop's per-symbol
    isolation added earlier this session, _total_committed treating an
    unreadable cost_basis as $0 instead of blocking) -- just never
    applied here, the one place a single corrupted line could silently
    freeze the public dashboard for the rest of the hackathon week."""
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text().strip().splitlines()
    records = []
    for i, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f"  WARNING: decision_log.jsonl line {i} is not valid JSON ({e}) -- skipping it, not aborting the whole read")
    return list(reversed(records))[:limit]
