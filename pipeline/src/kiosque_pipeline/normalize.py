"""
normalize.py — raw → bronze.

Merges one day's per-media raw files into a single deduplicated article list,
restricted to the 24h window ending at the collection's finished_at.
"""

import hashlib
import html
import logging
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from kiosque_pipeline import layers
from kiosque_pipeline.context import JobContext

logger = logging.getLogger(__name__)

WINDOW_BEFORE = timedelta(hours=24)
WINDOW_AFTER = timedelta(hours=1)
MIN_TITLE_WORDS = 4
TRACKING_PARAMS = {"xtor", "fbclid", "gclid"}
TRACKING_PREFIXES = ("utm_", "at_")
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class RawDataMissing(Exception):
    """The collector's _report.json for the run date does not exist."""


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def canonical_url(url: str) -> str:
    parts = urlsplit(url.strip())
    query = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in TRACKING_PARAMS and not k.lower().startswith(TRACKING_PREFIXES)
    ]
    path = parts.path
    if len(path) > 1:
        path = path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path or "/", urlencode(query), ""))


def clean_title(title: str) -> str:
    return " ".join(html.unescape(title).replace("\xa0", " ").split())


def _in_window(date: str | None, reference_time: datetime) -> bool:
    if date is None:
        return True
    ts = _parse_ts(date)
    return reference_time - WINDOW_BEFORE <= ts <= reference_time + WINDOW_AFTER


def normalize_articles(raw_files: list[dict], reference_time: datetime, known_slugs: set[str]) -> list[dict]:
    by_url: dict[str, dict] = {}
    for raw in raw_files:
        media = raw["media"]
        if media not in known_slugs:
            logger.warning("Skipping raw file for unknown media '%s'", media)
            continue
        for article in raw["articles"]:
            title = clean_title(article.get("title") or "")
            if len(title.split()) < MIN_TITLE_WORDS:
                continue
            date = article.get("date")
            if not _in_window(date, reference_time):
                continue
            url = canonical_url(article["url"])
            candidate = {
                "id": hashlib.sha1(url.encode("utf-8")).hexdigest()[:16],
                "media": media,
                "title": title,
                "url": url,
                "date": date,
                "source_method": raw.get("source_method", "unknown"),
            }
            existing = by_url.get(url)
            if existing is None or (date is not None and (existing["date"] is None or date < existing["date"])):
                by_url[url] = candidate
    return sorted(by_url.values(), key=lambda a: (a["media"], a["url"]))


def run(ctx: JobContext) -> dict:
    report_path = layers.raw_report(ctx.run_date)
    if not ctx.storage.exists(report_path):
        raise RawDataMissing(f"{report_path} not found — did the collector run on {ctx.run_date}?")
    report = ctx.storage.read_json(report_path)

    raw_files = [
        ctx.storage.read_json(path)
        for path in ctx.storage.list(layers.raw_dir(ctx.run_date))
        if not path.endswith("/_report.json")
    ]
    reference_time = _parse_ts(report["finished_at"])
    articles = normalize_articles(raw_files, reference_time, set(ctx.sources_by_slug))

    ctx.storage.write_json(layers.bronze_articles(ctx.run_date), {
        "run_date": ctx.run_date,
        "reference_time": reference_time.strftime(TS_FORMAT),
        "collection": {
            "total_sources": report["total_sources"],
            "success_count": report["success_count"],
            "failed": sorted(s["slug"] for s in report["sources"] if s["status"] == "error"),
        },
        "articles": articles,
    })
    logger.info("Normalized %d articles from %d raw files", len(articles), len(raw_files))
    return {"articles": len(articles)}
