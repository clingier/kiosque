"""layers.py — Where each medallion document lives, keyed by run date (YYYY-MM-DD)."""

WEB_LATEST = "$web/snapshot.json"


def raw_dir(run_date: str) -> str:
    return f"raw/feeds/{run_date}"


def raw_report(run_date: str) -> str:
    return f"raw/feeds/{run_date}/_report.json"


def bronze_articles(run_date: str) -> str:
    return f"bronze/articles/{run_date}.json"


def silver_stories(run_date: str) -> str:
    return f"silver/stories/{run_date}.json"


def silver_enriched(run_date: str) -> str:
    return f"silver/enriched/{run_date}.json"


def gold_metrics(run_date: str) -> str:
    return f"gold/metrics/{run_date}.json"


def gold_snapshot(run_date: str) -> str:
    return f"gold/snapshots/{run_date}.json"


def web_archive(run_date: str) -> str:
    return f"$web/snapshots/{run_date}.json"
