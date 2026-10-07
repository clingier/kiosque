"""job.py — Shared job settings: run-date resolution and the storage secret location."""

from datetime import date, datetime

SECRET_SCOPE = "kiosque"
SECRET_KEY = "datalake-connection-string"

def resolve_run_date(value: str, now: datetime) -> str:
    value = value.strip()
    if not value:
        return now.strftime("%Y-%m-%d")
    return date.fromisoformat(value).isoformat()
