"""
function_app.py — Azure Function App entry point (v2 programming model).

Timer-triggered function that runs daily at 06:00 UTC to collect
articles from all media sources configured in sources.yaml.
"""

import logging
from datetime import datetime, timezone

import azure.functions as func

from collector import run_collection
from freshness import check
from storage import StorageWriter

app = func.FunctionApp()

logger = logging.getLogger(__name__)


@app.timer_trigger(
    schedule="0 0 6 * * *",  # Every day at 06:00 UTC
    arg_name="timer",
    run_on_startup=False,
)
def collect_feeds(timer: func.TimerRequest) -> None:
    """
    Daily feed collection trigger.

    Reads sources.yaml, collects articles from all media sources configured in sources.yaml,
    and writes results to ADLS Gen2 raw/feeds/YYYY-MM-DD/.
    """
    if timer.past_due:
        logger.warning("Timer trigger is past due — running catch-up collection")

    logger.info("Starting daily feed collection")

    try:
        report = run_collection()

        logger.info(
            "Collection finished: %d/%d sources OK, %d articles, %ds",
            report["success_count"],
            report["total_sources"],
            report["total_articles"],
            report["duration_seconds"],
        )
    except Exception as e:
        logger.error("Collection failed with unhandled exception: %s", e, exc_info=True)
        raise


@app.timer_trigger(
    schedule="0 30 7 * * *",  # Every day at 07:30 UTC, after the Databricks job
    arg_name="timer",
    run_on_startup=False,
)
def check_snapshot_freshness(timer: func.TimerRequest) -> None:
    """Log a STALE SNAPSHOT error (alerted on in App Insights) if today's snapshot is missing."""
    snapshot = StorageWriter.from_env().read_json("$web", "snapshot.json")
    reason = check(snapshot, datetime.now(timezone.utc))
    if reason:
        logger.error("STALE SNAPSHOT: %s", reason)
    else:
        logger.info("Snapshot is fresh")
