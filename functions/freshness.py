"""
freshness.py — Detect a stale $web/snapshot.json.

The site's snapshot must carry today's (UTC) date once the daily pipeline
has had time to run.
"""

from datetime import datetime


def check(snapshot: dict | None, now: datetime) -> str | None:
    """Return None if the snapshot is fresh, otherwise a human-readable reason."""
    if snapshot is None:
        return "snapshot.json not found in $web"
    expected = now.strftime("%Y-%m-%d")
    actual = snapshot.get("date")
    if actual != expected:
        return f"snapshot.json is dated {actual}, expected {expected}"
    return None
