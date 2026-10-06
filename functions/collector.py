"""
collector.py — Core collection logic for Kiosque.

Orchestrates the feed hierarchy (RSS → sitemap → gnews fallback) across
all media sources configured in sources.yaml, with async parallelism, retry, and reporting.
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import yaml

from parsers.rss import parse_rss
from parsers.sitemap import parse_sitemap
from parsers.gnews import parse_gnews
from storage import StorageWriter

logger = logging.getLogger(__name__)

# Concurrency limit for parallel HTTP requests
MAX_CONCURRENT_REQUESTS = 10

# Retry configuration
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1  # seconds: 1s, 2s, 4s

# HTTP timeout per request (seconds)
REQUEST_TIMEOUT = 15


def load_sources(config_path: str | None = None) -> list[dict]:
    """Load the sources.yaml configuration file."""
    if config_path is None:
        # Look relative to this file, then in config/
        here = Path(__file__).parent
        candidates = [
            here / "config" / "sources.yaml",
            here.parent / "config" / "sources.yaml",
            Path("config") / "sources.yaml",
        ]
        for candidate in candidates:
            if candidate.exists():
                config_path = str(candidate)
                break
        else:
            raise FileNotFoundError(
                "sources.yaml not found. Searched: "
                + ", ".join(str(c) for c in candidates)
            )

    with open(config_path, "r", encoding="utf-8") as f:
        sources = yaml.safe_load(f)

    logger.info("Loaded %d sources from %s", len(sources), config_path)
    return sources


def _collect_one_sync(source: dict) -> dict:
    """
    Collect articles for a single media source (synchronous).

    Applies the feed hierarchy:
    1. Try each feed in order (rss/atom, then sitemap)
    2. If all feeds fail and fallback_domain exists, try gnews
    3. If everything fails, return an error result

    Returns a result dict with status, articles, timing, etc.
    """
    slug = source["slug"]
    start_time = time.monotonic()
    feeds = source.get("feeds", [])
    fallback_domain = source.get("fallback_domain", "")

    # Try each configured feed in order
    for feed in feeds:
        feed_url = feed["url"]
        feed_type = feed["type"]

        articles = _try_feed_with_retry(feed_url, feed_type, slug)
        if articles:
            elapsed_ms = int((time.monotonic() - start_time) * 1000)
            return {
                "slug": slug,
                "status": "ok",
                "source_method": feed_type,
                "feed_url": feed_url,
                "article_count": len(articles),
                "articles": articles,
                "duration_ms": elapsed_ms,
            }

    # All native feeds failed — try Google News fallback
    if fallback_domain:
        try:
            articles = parse_gnews(fallback_domain, slug, timeout=REQUEST_TIMEOUT)
            if articles:
                elapsed_ms = int((time.monotonic() - start_time) * 1000)
                return {
                    "slug": slug,
                    "status": "ok",
                    "source_method": "gnews",
                    "feed_url": f"gnews:{fallback_domain}",
                    "article_count": len(articles),
                    "articles": articles,
                    "duration_ms": elapsed_ms,
                }
        except Exception as e:
            logger.warning(
                "Google News fallback failed for %s (%s): %s",
                slug,
                fallback_domain,
                e,
            )

    # Everything failed
    elapsed_ms = int((time.monotonic() - start_time) * 1000)
    error_msg = "All feeds and fallback failed"
    if not feeds and not fallback_domain:
        error_msg = "No feeds configured and no fallback domain"
    elif not feeds:
        error_msg = "No feeds configured, gnews fallback failed"

    logger.warning("Collection failed for %s: %s", slug, error_msg)
    return {
        "slug": slug,
        "status": "error",
        "error": error_msg,
        "source_method": feeds[0]["type"] if feeds else "none",
        "feed_url": feeds[0]["url"] if feeds else "",
        "article_count": 0,
        "articles": [],
        "attempts": MAX_RETRIES if feeds else 0,
        "duration_ms": elapsed_ms,
    }


def _try_feed_with_retry(url: str, feed_type: str, slug: str) -> list[dict]:
    """
    Try to parse a feed with exponential backoff retry.

    Retries apply to the HTTP fetch level. Parse errors are immediate
    and definitive (no retry).

    Returns a list of articles, or empty list on failure.
    """
    for attempt in range(MAX_RETRIES):
        try:
            if feed_type in ("rss", "atom"):
                articles = parse_rss(url, slug, timeout=REQUEST_TIMEOUT)
            elif feed_type == "sitemap":
                articles = parse_sitemap(url, slug, timeout=REQUEST_TIMEOUT)
            else:
                logger.warning("Unknown feed type '%s' for %s", feed_type, slug)
                return []

            if articles:
                return articles

            # Empty result — might be temporary, retry
            if attempt < MAX_RETRIES - 1:
                backoff = RETRY_BACKOFF_BASE * (2**attempt)
                logger.info(
                    "Empty result for %s feed %s, retrying in %ds (attempt %d/%d)",
                    slug,
                    url,
                    backoff,
                    attempt + 1,
                    MAX_RETRIES,
                )
                time.sleep(backoff)
            continue

        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                backoff = RETRY_BACKOFF_BASE * (2**attempt)
                logger.warning(
                    "Error fetching %s for %s: %s. Retrying in %ds (attempt %d/%d)",
                    url,
                    slug,
                    e,
                    backoff,
                    attempt + 1,
                    MAX_RETRIES,
                )
                time.sleep(backoff)
            else:
                logger.error(
                    "Failed to fetch %s for %s after %d attempts: %s",
                    url,
                    slug,
                    MAX_RETRIES,
                    e,
                )

    return []


async def _collect_one_async(
    source: dict, semaphore: asyncio.Semaphore, loop: asyncio.AbstractEventLoop
) -> dict:
    """
    Async wrapper around _collect_one_sync.

    Uses a semaphore to limit concurrency and runs the synchronous
    parsers in a thread pool to avoid blocking the event loop.
    """
    async with semaphore:
        return await loop.run_in_executor(None, _collect_one_sync, source)


async def collect_all_async(sources: list[dict]) -> list[dict]:
    """
    Collect articles from all sources in parallel with bounded concurrency.

    Returns a list of result dicts (one per source).
    """
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    loop = asyncio.get_event_loop()

    tasks = [
        _collect_one_async(source, semaphore, loop) for source in sources
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert any exceptions to error results
    processed = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            slug = sources[i].get("slug", f"unknown-{i}")
            logger.error("Unexpected error collecting %s: %s", slug, result)
            processed.append(
                {
                    "slug": slug,
                    "status": "error",
                    "error": str(result),
                    "source_method": "none",
                    "feed_url": "",
                    "article_count": 0,
                    "articles": [],
                    "duration_ms": 0,
                }
            )
        else:
            processed.append(result)

    return processed


def build_report(
    results: list[dict],
    started_at: datetime,
    finished_at: datetime,
) -> dict:
    """Build the _report.json summary from collection results."""
    success_count = sum(1 for r in results if r["status"] == "ok")
    failure_count = sum(1 for r in results if r["status"] == "error")
    total_articles = sum(r.get("article_count", 0) for r in results)
    duration = (finished_at - started_at).total_seconds()

    # Build per-source summary (without the full articles list)
    source_summaries = []
    for r in results:
        summary = {
            "slug": r["slug"],
            "status": r["status"],
            "source_method": r.get("source_method", "none"),
            "article_count": r.get("article_count", 0),
            "duration_ms": r.get("duration_ms", 0),
        }
        if r["status"] == "error":
            summary["error"] = r.get("error", "Unknown error")
            summary["attempts"] = r.get("attempts", 0)
        source_summaries.append(summary)

    report = {
        "date": started_at.strftime("%Y-%m-%d"),
        "started_at": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "finished_at": finished_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration_seconds": int(duration),
        "total_sources": len(results),
        "success_count": success_count,
        "failure_count": failure_count,
        "total_articles": total_articles,
        "sources": source_summaries,
    }

    return report


def run_collection(
    config_path: str | None = None,
    writer: StorageWriter | None = None,
) -> dict:
    """
    Main entry point: load sources, collect all, write results, return report.

    This is the function called by the Azure Function timer trigger
    and by the CLI for local testing.
    """
    started_at = datetime.now(timezone.utc)
    date_str = started_at.strftime("%Y-%m-%d")

    # Load sources
    sources = load_sources(config_path)

    # Initialize storage writer
    if writer is None:
        writer = StorageWriter.from_env()

    # Run async collection
    results = asyncio.run(collect_all_async(sources))

    finished_at = datetime.now(timezone.utc)

    # Write individual source files
    for result in results:
        if result["status"] == "ok" and result["article_count"] > 0:
            slug = result["slug"]
            output_data = {
                "media": slug,
                "collected_at": finished_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source_method": result["source_method"],
                "feed_url": result.get("feed_url", ""),
                "article_count": result["article_count"],
                "articles": [
                    {
                        "title": a["title"],
                        "url": a["url"],
                        "date": a["date"],
                    }
                    for a in result["articles"]
                ],
            }
            blob_path = f"feeds/{date_str}/{slug}.json"
            writer.write(blob_path, output_data)
            logger.info("Wrote %d articles for %s", result["article_count"], slug)

    # Build and write report
    report = build_report(results, started_at, finished_at)
    report_path = f"feeds/{date_str}/_report.json"
    writer.write(report_path, report)

    # Alert if too many failures
    failure_count = report["failure_count"]
    if failure_count > 5:
        logger.error(
            "HIGH FAILURE RATE: %d/%d sources failed during collection on %s",
            failure_count,
            report["total_sources"],
            date_str,
        )
    else:
        logger.info(
            "Collection complete: %d/%d sources OK, %d articles total, %ds elapsed",
            report["success_count"],
            report["total_sources"],
            report["total_articles"],
            report["duration_seconds"],
        )

    return report
