from datetime import datetime, timezone

import pytest

from kiosque_pipeline import job
from conftest import REPO_ROOT


def test_resolve_run_date_defaults_to_today_utc():
    now = datetime(2026, 10, 6, 6, 20, tzinfo=timezone.utc)
    assert job.resolve_run_date("", now) == "2026-10-06"
    assert job.resolve_run_date("  ", now) == "2026-10-06"


def test_resolve_run_date_accepts_explicit_date():
    assert job.resolve_run_date("2026-10-01", datetime.now(timezone.utc)) == "2026-10-01"


def test_resolve_run_date_rejects_garbage():
    with pytest.raises(ValueError):
        job.resolve_run_date("06/10/2026", datetime.now(timezone.utc))


class FakeDbutils:
    class widgets:
        values = {"run_date": "2026-10-01", "config_dir": str(REPO_ROOT / "config")}

        @classmethod
        def get(cls, name):
            return cls.values[name]

    class secrets:
        @staticmethod
        def get(scope, key):
            assert (scope, key) == ("kiosque", "datalake-connection-string")
            return "conn-string"


def test_job_context(monkeypatch):
    monkeypatch.setattr(job, "BlobStorage", lambda conn: ("blob", conn))
    ctx = job.job_context(FakeDbutils)
    assert ctx.run_date == "2026-10-01"
    assert ctx.storage == ("blob", "conn-string")
    assert len(ctx.sources) >= 60
    assert len(ctx.major_groups) == 6
