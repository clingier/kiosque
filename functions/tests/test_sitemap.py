"""Tests for parsers/sitemap.py — Google News Sitemap parser."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock
from xml.etree import ElementTree as ET

import pytest

# Add functions/ to the path so we can import parsers
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.sitemap import parse_sitemap, _parse_news_sitemap, _parse_date, NS

FIXTURES = Path(__file__).parent / "fixtures"

# Fixtures have dates around July 3 2026 — freeze "now" so freshness filter works
FIXTURE_NOW = datetime(2026, 7, 3, 8, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _freeze_sitemap_time():
    """Set a very large freshness window so fixture dates always count as fresh."""
    with patch("parsers.sitemap.FRESHNESS_WINDOW_HOURS", 999999):
        yield


# ──────────────────────────────────────────────────────────────────────
# Unit tests for _parse_date
# ──────────────────────────────────────────────────────────────────────


class TestParseDateSitemap:
    def test_full_datetime_with_tz(self):
        result = _parse_date("2026-07-03T08:30:00+02:00")
        assert result == "2026-07-03T06:30:00Z"

    def test_date_only(self):
        result = _parse_date("2026-07-03")
        assert result == "2026-07-03T00:00:00Z"

    def test_none_returns_none(self):
        assert _parse_date(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_date("") is None

    def test_invalid_date_returns_none(self):
        assert _parse_date("not-a-date") is None


# ──────────────────────────────────────────────────────────────────────
# Integration tests with fixtures
# ──────────────────────────────────────────────────────────────────────


class TestParseSitemapStandard:
    """Test with a standard Google News Sitemap fixture."""

    def _get_articles(self):
        """Parse the standard sitemap fixture via _parse_news_sitemap."""
        fixture_path = FIXTURES / "sitemap_standard.xml"
        tree = ET.parse(fixture_path)
        root = tree.getroot()
        cutoff = FIXTURE_NOW - timedelta(hours=48)
        return _parse_news_sitemap(root, "les-echos", str(fixture_path), cutoff)

    def test_parses_fresh_articles(self):
        articles = self._get_articles()
        # Should have 3 fresh articles (4th is > 48h old)
        assert len(articles) == 3

    def test_article_structure(self):
        articles = self._get_articles()
        for article in articles:
            assert article["media"] == "les-echos"
            assert article["source_method"] == "sitemap"
            assert "title" in article
            assert "url" in article
            assert "date" in article
            assert article["url"].startswith("https://")

    def test_titles_extracted(self):
        articles = self._get_articles()
        titles = [a["title"] for a in articles]
        assert any("croissance" in t.lower() for t in titles)
        assert any("CAC 40" in t for t in titles)

    def test_dates_are_utc(self):
        articles = self._get_articles()
        for article in articles:
            assert article["date"].endswith("Z")

    def test_old_articles_filtered(self):
        articles = self._get_articles()
        urls = [a["url"] for a in articles]
        assert not any("article_old" in url for url in urls)


class TestParseSitemapIndex:
    """Test sitemap index detection and handling."""

    def test_detects_sitemap_index(self):
        """Verify that _fetch_xml-based logic would detect sitemapindex."""
        fixture_path = FIXTURES / "sitemap_index.xml"
        tree = ET.parse(fixture_path)
        root = tree.getroot()
        root_tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
        assert root_tag == "sitemapindex"

    def test_finds_sub_sitemaps(self):
        fixture_path = FIXTURES / "sitemap_index.xml"
        tree = ET.parse(fixture_path)
        root = tree.getroot()
        sub_sitemaps = root.findall("sm:sitemap", NS)
        assert len(sub_sitemaps) == 3

    def test_filters_old_sub_sitemaps(self):
        """The third sub-sitemap (May 2026) should be filtered out."""
        fixture_path = FIXTURES / "sitemap_index.xml"
        tree = ET.parse(fixture_path)
        root = tree.getroot()
        cutoff = FIXTURE_NOW - timedelta(hours=48)

        fresh_count = 0
        for sitemap_elem in root.findall("sm:sitemap", NS):
            lastmod = sitemap_elem.findtext("sm:lastmod", namespaces=NS)
            if lastmod:
                parsed = _parse_date(lastmod)
                if parsed:
                    dt = datetime.fromisoformat(parsed.replace("Z", "+00:00"))
                    if dt >= cutoff:
                        fresh_count += 1

        # Only 2 of the 3 sub-sitemaps should be recent
        assert fresh_count == 2


class TestParseSitemapEmpty:
    """Test with a sitemap without news namespace."""

    def test_no_news_namespace_returns_empty(self):
        fixture_path = FIXTURES / "sitemap_empty.xml"
        tree = ET.parse(fixture_path)
        root = tree.getroot()
        cutoff = FIXTURE_NOW - timedelta(hours=48)
        articles = _parse_news_sitemap(root, "test-media", str(fixture_path), cutoff)
        # No title available without news namespace → empty
        assert articles == []
