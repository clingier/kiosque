from datetime import datetime, timezone

import pytest

from kiosque_pipeline import job


def test_resolve_run_date_defaults_to_today_utc():
    now = datetime(2026, 10, 6, 6, 20, tzinfo=timezone.utc)
    assert job.resolve_run_date("", now) == "2026-10-06"
    assert job.resolve_run_date("  ", now) == "2026-10-06"


def test_resolve_run_date_accepts_explicit_date():
    assert job.resolve_run_date("2026-10-01", datetime.now(timezone.utc)) == "2026-10-01"


def test_resolve_run_date_rejects_garbage():
    with pytest.raises(ValueError):
        job.resolve_run_date("06/10/2026", datetime.now(timezone.utc))
