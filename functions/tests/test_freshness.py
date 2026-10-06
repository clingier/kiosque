"""Tests for freshness.py — stale snapshot detection."""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from freshness import check

NOW = datetime(2026, 10, 6, 7, 30, tzinfo=timezone.utc)


def test_todays_snapshot_is_fresh():
    assert check({"date": "2026-10-06"}, NOW) is None


def test_yesterdays_snapshot_is_stale():
    assert check({"date": "2026-10-05"}, NOW) == "snapshot.json is dated 2026-10-05, expected 2026-10-06"


def test_missing_snapshot_is_stale():
    assert check(None, NOW) == "snapshot.json not found in $web"


def test_snapshot_without_date_is_stale():
    assert check({}, NOW) == "snapshot.json is dated None, expected 2026-10-06"
