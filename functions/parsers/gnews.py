"""
parsers/gnews.py — Google News RSS fallback parser for Kiosque.

Builds and parses a Google News RSS feed scoped to a specific domain.
Used as a fallback when a media has no native RSS or sitemap feed.
"""

import logging
import re
import time

import feedparser

from parsers.rss import _clean_title, _parse_date, _is_fresh, FRESHNESS_WINDOW_HOURS

from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Google News RSS URL template
GNEWS_URL_TEMPLATE = (
    "https://news.google.com/rss/search"
    "?q=site:{domain}&hl=fr&gl=FR&ceid=FR:fr"
)

# Delay between Google News requests to avoid rate limiting (seconds)
GNEWS_RATE_LIMIT_DELAY = 1.5

# Regex to strip the " - MediaName" suffix Google appends to titles
RE_TITLE_SUFFIX = re.compile(r"\s*-\s*[^-]+$")

# Track last request time for rate limiting
_last_request_time: float = 0.0


def _strip_source_suffix(title: str, domain: str) -> str:
    """
    Remove the " - Source Name" suffix that Google News appends to titles.

    For example: "Article title - Le Monde" → "Article title"
    """
    if not title:
        return title

    # Google typically appends " - SourceName" at the end
    match = RE_TITLE_SUFFIX.search(title)
    if match:
        return title[: match.start()].strip()

    return title


def parse_gnews(domain: str, slug: str, timeout: int = 15) -> list[dict]:
    """
    Build and parse the Google News RSS feed for a domain.

    Returns a list of normalised article dicts with source_method="gnews".
    This is a fallback parser — data is less reliable than native feeds.

    Args:
        domain: Bare domain (e.g. "cnews.fr") to scope the Google News search.
        slug: Media slug identifier.
        timeout: HTTP request timeout in seconds.

    Returns:
        List of article dicts, or empty list on failure.
    """
    global _last_request_time

    url = GNEWS_URL_TEMPLATE.format(domain=domain)
    articles = []
    seen_urls = set()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=FRESHNESS_WINDOW_HOURS)

    # Rate limiting — wait if needed
    elapsed = time.time() - _last_request_time
    if elapsed < GNEWS_RATE_LIMIT_DELAY:
        time.sleep(GNEWS_RATE_LIMIT_DELAY - elapsed)

    try:
        feed = feedparser.parse(
            url,
            request_headers={"User-Agent": "Kiosque/1.0 (media-monitor)"},
        )
        _last_request_time = time.time()
    except Exception as e:
        logger.warning(
            "Failed to fetch Google News feed for %s (%s): %s", slug, domain, e
        )
        _last_request_time = time.time()
        return []

    # Check for HTTP errors
    status = feed.get("status", 0)
    if status and status >= 400:
        logger.warning(
            "Google News feed for %s (%s) returned HTTP %d", slug, domain, status
        )
        return []

    if feed.bozo and not feed.entries:
        logger.warning(
            "Google News feed for %s (%s) is malformed: %s",
            slug,
            domain,
            feed.get("bozo_exception", "Unknown error"),
        )
        return []

    for entry in feed.entries:
        # Extract and clean title
        raw_title = entry.get("title", "")
        title = _clean_title(raw_title)
        title = _strip_source_suffix(title, domain)

        if not title:
            continue

        # Extract URL
        link = entry.get("link", "")
        if not link:
            continue

        # Google News often wraps URLs in a redirect — use the direct link if available
        # The <source url="..."> in Google News RSS gives the real URL
        source = entry.get("source", {})
        if isinstance(source, dict) and source.get("href"):
            # feedparser puts the source URL in source.href
            pass  # The link field already points to the real article in most cases

        # Deduplicate
        if link in seen_urls:
            continue
        seen_urls.add(link)

        # Parse date
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
                "source_method": "gnews",
            }
        )

    logger.info(
        "Parsed %d articles from Google News for %s (%s)",
        len(articles),
        slug,
        domain,
    )
    return articles
