"""
function_app.py — Azure Function App entry point (v2 programming model).

Timer-triggered function that runs daily at 06:00 UTC to collect
articles from all media sources configured in sources.yaml.
"""

import logging
import azure.functions as func

from collector import run_collection

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
