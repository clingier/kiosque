"""
parsers/rss.py — RSS/Atom feed parser for Kiosque.

Fetches and parses RSS 2.0, Atom, and RSS 1.0/RDF feeds using feedparser.
Returns a list of normalised article dicts.
"""

import html
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

import chardet
import feedparser
from dateutil import parser as dateutil_parser
from dateutil.tz import gettz

logger = logging.getLogger(__name__)

# Timezone for naive dates (most French media publish in Europe/Paris)
TZ_PARIS = gettz("Europe/Paris")

# Only keep articles from the last 48 hours
FRESHNESS_WINDOW_HOURS = 48

# Regex to strip residual HTML tags from titles
RE_HTML_TAGS = re.compile(r"<[^>]+>")

# Regex to unwrap CDATA sections
RE_CDATA = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.DOTALL)


def _clean_title(raw_title: str) -> str:
    """Clean a feed entry title: strip CDATA, HTML tags, entities, whitespace."""
    if not raw_title:
        return ""

    title = raw_title

    # Unwrap CDATA if present
    match = RE_CDATA.search(title)
    if match:
        title = match.group(1)

    # Strip HTML tags
    title = RE_HTML_TAGS.sub("", title)

    # Decode HTML entities (&amp; → &, &#39; → ', etc.)
    title = html.unescape(title)

    # Normalise whitespace
    title = " ".join(title.split()).strip()

    return title


def _parse_date(entry: dict) -> str:
    """
    Extract and normalise a date from a feedparser entry to ISO 8601 UTC.

    Strategy:
    1. Use feedparser's parsed date (struct_time) if available.
    2. Fallback to dateutil parsing of the raw date string.
    3. If no date at all, use current UTC time.
    4. If the date is timezone-naive, assume Europe/Paris.
    """
    # feedparser provides published_parsed or updated_parsed as struct_time
    parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")

    if parsed_time:
        try:
            dt = datetime(*parsed_time[:6], tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, TypeError):
            pass

    # Try raw date strings
    raw_date = entry.get("published") or entry.get("updated")
    if raw_date:
        try:
            dt = dateutil_parser.parse(raw_date)
            # If naive, assume Paris timezone
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TZ_PARIS)
            # Convert to UTC
            dt = dt.astimezone(timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, TypeError):
            pass

    # No date found — use current UTC time
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_fresh(date_str: str, cutoff: datetime) -> bool:
    """Check if an article date is within the freshness window."""
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt >= cutoff
    except (ValueError, TypeError):
        # If we can't parse it, keep the article (conservative)
        return True


def parse_rss(url: str, slug: str, timeout: int = 15) -> list[dict]:
    """
    Fetch and parse an RSS/Atom feed.

    Returns a list of normalised article dicts:
    {
        "media": str,        # slug of the media
        "title": str,        # cleaned title (no HTML, no CDATA)
        "url": str,          # link to the article
        "date": str,         # ISO 8601 UTC (e.g. "2026-07-03T08:30:00Z")
        "source_method": "rss"
    }

    Returns an empty list if the feed is inaccessible or empty.
    Raises an exception only on non-recoverable network errors.
    """
    articles = []
    seen_urls = set()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=FRESHNESS_WINDOW_HOURS)

    try:
        # feedparser handles fetching and parsing in one call
        feed = feedparser.parse(
            url,
            request_headers={"User-Agent": "Kiosque/1.0 (media-monitor)"},
        )
    except Exception as e:
        logger.warning("Failed to fetch RSS feed %s for %s: %s", url, slug, e)
        return []

    # Check for HTTP errors
    status = feed.get("status", 0)
    if status and status >= 400:
        logger.warning(
            "RSS feed %s for %s returned HTTP %d", url, slug, status
        )
        return []

    # Check if feed has any content (might be HTML instead of XML)
    if feed.bozo and not feed.entries:
        bozo_exception = feed.get("bozo_exception", "Unknown parse error")
        logger.warning(
            "RSS feed %s for %s is malformed: %s", url, slug, bozo_exception
        )
        return []

    # Check for encoding issues — if feedparser failed, try chardet
    if feed.bozo and hasattr(feed.bozo_exception, "getMessage"):
        # feedparser had trouble, but we have some entries — proceed cautiously
        logger.info(
            "RSS feed %s for %s had parse warnings (bozo), proceeding with %d entries",
            url,
            slug,
            len(feed.entries),
        )

    for entry in feed.entries:
        # Extract title — skip entries without one
        title = _clean_title(entry.get("title", ""))
        if not title:
            continue

        # Extract URL — skip entries without one
        link = entry.get("link", "")
        if not link:
            continue

        # Resolve relative URLs
        if not link.startswith(("http://", "https://")):
            base_url = feed.feed.get("link", url)
            link = urljoin(base_url, link)

        # Deduplicate by URL within this feed
        if link in seen_urls:
            continue
        seen_urls.add(link)

        # Parse and normalise date
        date_str = _parse_date(entry)

        # Filter by freshness
        if not _is_fresh(date_str, cutoff):
            continue

        articles.append(
            {
                "media": slug,
                "title": title,
                "url": link,
                "date": date_str,
                "source_method": "rss",
            }
        )

    logger.info(
        "Parsed %d articles from RSS feed %s for %s", len(articles), url, slug
    )
    return articles
