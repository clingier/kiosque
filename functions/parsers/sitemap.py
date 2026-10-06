"""
parsers/sitemap.py — Google News Sitemap parser for Kiosque.

Parses news-sitemap.xml files conforming to the Google News Sitemap protocol.
Handles both individual sitemaps and sitemap index files.
"""

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import requests

logger = logging.getLogger(__name__)

# XML namespaces for Google News Sitemaps
NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "news": "http://www.google.com/schemas/sitemap-news/0.9",
}

# Only keep articles from the last 48 hours
FRESHNESS_WINDOW_HOURS = 48


def _fetch_xml(url: str, timeout: int) -> ET.Element | None:
    """Fetch and parse an XML document. Returns the root element or None."""
    try:
        response = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Kiosque/1.0 (media-monitor)"},
        )
        response.raise_for_status()

        # Check content type — should be XML
        content_type = response.headers.get("Content-Type", "")
        if "html" in content_type.lower() and "xml" not in content_type.lower():
            logger.warning(
                "Sitemap %s returned HTML instead of XML (Content-Type: %s)",
                url,
                content_type,
            )
            return None

        return ET.fromstring(response.content)
    except requests.exceptions.RequestException as e:
        logger.warning("Failed to fetch sitemap %s: %s", url, e)
        return None
    except ET.ParseError as e:
        logger.warning("Failed to parse sitemap XML %s: %s", url, e)
        return None


def _parse_date(date_str: str | None) -> str | None:
    """
    Parse a sitemap date string to ISO 8601 UTC.

    Sitemap dates can be:
    - Full datetime: 2026-07-03T08:30:00+02:00
    - Date only: 2026-07-03
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    try:
        # Try full datetime with timezone
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str)
            if dt.tzinfo is None:
                # Assume Paris timezone for naive datetimes
                from dateutil.tz import gettz

                dt = dt.replace(tzinfo=gettz("Europe/Paris"))
            dt = dt.astimezone(timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            # Date only — assume end of day UTC, so the article falls in exactly
            # one daily collection window (the one after that day ends)
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            dt = dt.replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, TypeError):
        return None


def _is_fresh(date_str: str | None, cutoff: datetime) -> bool:
    """Check if a date string is within the freshness window."""
    if not date_str:
        # If we can't determine the date, keep the article (conservative)
        return True
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt >= cutoff
    except (ValueError, TypeError):
        return True


def _parse_news_sitemap(
    root: ET.Element, slug: str, base_url: str, cutoff: datetime
) -> list[dict]:
    """Parse a single news sitemap XML tree into article dicts."""
    articles = []
    seen_urls = set()

    for url_elem in root.findall("sm:url", NS):
        # Extract the article URL
        loc = url_elem.findtext("sm:loc", namespaces=NS)
        if not loc:
            continue

        # Resolve relative URLs
        if not loc.startswith(("http://", "https://")):
            loc = urljoin(base_url, loc)

        # Deduplicate
        if loc in seen_urls:
            continue
        seen_urls.add(loc)

        # Look for news:news element
        news_elem = url_elem.find("news:news", NS)

        title = None
        date_str = None

        if news_elem is not None:
            title = news_elem.findtext("news:title", namespaces=NS)
            date_str = news_elem.findtext(
                "news:publication_date", namespaces=NS
            )
        else:
            # No news namespace — try lastmod as date
            date_str = url_elem.findtext("sm:lastmod", namespaces=NS)

        # Parse date
        parsed_date = _parse_date(date_str)

        # Filter by freshness
        if not _is_fresh(parsed_date, cutoff):
            continue

        # Skip entries without a title
        if not title:
            continue

        # Use current UTC time if no date available
        if not parsed_date:
            parsed_date = datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

        articles.append(
            {
                "media": slug,
                "title": title.strip(),
                "url": loc,
                "date": parsed_date,
                "source_method": "sitemap",
            }
        )

    return articles


def parse_sitemap(url: str, slug: str, timeout: int = 15) -> list[dict]:
    """
    Fetch and parse a Google News Sitemap.

    Handles both individual news sitemaps and sitemap index files.
    Returns a list of normalised article dicts with source_method="sitemap".

    Returns an empty list if the sitemap is inaccessible or empty.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=FRESHNESS_WINDOW_HOURS)

    root = _fetch_xml(url, timeout)
    if root is None:
        return []

    # Strip namespace prefix from root tag for easier comparison
    root_tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag

    # Check if this is a sitemap index
    if root_tag == "sitemapindex":
        logger.info("Sitemap %s is a sitemap index, processing sub-sitemaps", url)
        return _parse_sitemap_index(root, slug, url, timeout, cutoff)

    # It's a regular sitemap (urlset)
    if root_tag == "urlset":
        articles = _parse_news_sitemap(root, slug, url, cutoff)
        logger.info(
            "Parsed %d articles from sitemap %s for %s",
            len(articles),
            url,
            slug,
        )
        return articles

    logger.warning(
        "Sitemap %s has unexpected root element: %s", url, root_tag
    )
    return []


def _parse_sitemap_index(
    root: ET.Element,
    slug: str,
    base_url: str,
    timeout: int,
    cutoff: datetime,
) -> list[dict]:
    """
    Process a sitemap index by fetching and parsing each sub-sitemap.

    Only processes sub-sitemaps whose lastmod is within the freshness window.
    """
    all_articles = []

    for sitemap_elem in root.findall("sm:sitemap", NS):
        loc = sitemap_elem.findtext("sm:loc", namespaces=NS)
        if not loc:
            continue

        # Resolve relative URLs
        if not loc.startswith(("http://", "https://")):
            loc = urljoin(base_url, loc)

        # Check lastmod — only process recent sub-sitemaps
        lastmod = sitemap_elem.findtext("sm:lastmod", namespaces=NS)
        if lastmod:
            parsed_lastmod = _parse_date(lastmod)
            if parsed_lastmod and not _is_fresh(parsed_lastmod, cutoff):
                logger.debug(
                    "Skipping sub-sitemap %s (lastmod %s is too old)", loc, lastmod
                )
                continue

        # Fetch and parse the sub-sitemap
        sub_root = _fetch_xml(loc, timeout)
        if sub_root is None:
            continue

        sub_articles = _parse_news_sitemap(sub_root, slug, loc, cutoff)
        all_articles.extend(sub_articles)

    logger.info(
        "Parsed %d articles from sitemap index %s for %s (%d sub-sitemaps)",
        len(all_articles),
        base_url,
        slug,
        len(root.findall("sm:sitemap", NS)),
    )
    return all_articles
