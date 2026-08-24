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


def read_log(limit: int = 30) -> List[Dict[str, Any]]:
    """Most recent `limit` records, newest first. Empty list if no log yet."""
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text().strip().splitlines()
    records = [json.loads(line) for line in lines if line.strip()]
    return list(reversed(records))[:limit]
