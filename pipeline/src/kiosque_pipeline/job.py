"""job.py — Build a JobContext inside a Databricks notebook."""

from datetime import date, datetime, timezone

from kiosque_pipeline.config import load_groups, load_sources, validate_config
from kiosque_pipeline.context import JobContext
from kiosque_pipeline.storage import BlobStorage

SECRET_SCOPE = "kiosque"
SECRET_KEY = "datalake-connection-string"


def resolve_run_date(value: str, now: datetime) -> str:
    value = value.strip()
    if not value:
        return now.strftime("%Y-%m-%d")
    return date.fromisoformat(value).isoformat()


def job_context(dbutils) -> JobContext:
    config_dir = dbutils.widgets.get("config_dir")
    sources = load_sources(f"{config_dir}/sources.yaml")
    groups = load_groups(f"{config_dir}/groups.yaml")
    validate_config(sources, groups)
    return JobContext(
        storage=BlobStorage(dbutils.secrets.get(scope=SECRET_SCOPE, key=SECRET_KEY)),
        run_date=resolve_run_date(dbutils.widgets.get("run_date"), datetime.now(timezone.utc)),
        sources=sources,
        groups=groups,
    )
