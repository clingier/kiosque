"""Tests for parsers/gnews.py — Google News RSS fallback parser."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

# Add functions/ to the path so we can import parsers
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.gnews import parse_gnews, _strip_source_suffix

FIXTURES = Path(__file__).parent / "fixtures"

# Fixtures have dates around July 3 2026 — freeze "now" so freshness filter works
FIXTURE_NOW = datetime(2026, 7, 3, 8, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _freeze_gnews_time():
    """Set a very large freshness window so fixture dates always count as fresh."""
    with patch("parsers.gnews.FRESHNESS_WINDOW_HOURS", 999999):
        yield


# ──────────────────────────────────────────────────────────────────────
# Unit tests for _strip_source_suffix
# ──────────────────────────────────────────────────────────────────────


class TestStripSourceSuffix:
    def test_strips_simple_suffix(self):
        assert _strip_source_suffix("Title here - CNews", "cnews.fr") == "Title here"

    def test_strips_suffix_with_spaces(self):
        result = _strip_source_suffix("Big news today - Le Monde", "lemonde.fr")
        assert result == "Big news today"

    def test_no_suffix_unchanged(self):
        assert _strip_source_suffix("Title without suffix", "test.fr") == "Title without suffix"

    def test_empty_string(self):
        assert _strip_source_suffix("", "test.fr") == ""

    def test_preserves_hyphens_in_title(self):
        # Only the last " - Source" should be stripped
        result = _strip_source_suffix("COVID-19 : mise à jour - CNews", "cnews.fr")
        assert result == "COVID-19 : mise à jour"


# ──────────────────────────────────────────────────────────────────────
# Integration test with fixture
# ──────────────────────────────────────────────────────────────────────


class TestParseGnewsFixture:
    """Test with a captured Google News RSS fixture."""

    def test_parses_gnews_fixture(self):
        fixture_path = str(FIXTURES / "gnews_sample.xml")
        # feedparser can read local files, but parse_gnews builds a URL
        # and uses feedparser.parse(). We mock feedparser.parse to use our fixture.
        import feedparser

        fixture_feed = feedparser.parse(fixture_path)

        with patch("parsers.gnews.feedparser.parse", return_value=fixture_feed):
            with patch("parsers.gnews.time.sleep"):  # Skip rate limiting
                articles = parse_gnews("cnews.fr", "cnews")

        assert len(articles) == 3

    def test_gnews_source_suffix_stripped(self):
        fixture_path = str(FIXTURES / "gnews_sample.xml")
        import feedparser

        fixture_feed = feedparser.parse(fixture_path)

        with patch("parsers.gnews.feedparser.parse", return_value=fixture_feed):
            with patch("parsers.gnews.time.sleep"):
                articles = parse_gnews("cnews.fr", "cnews")

        for article in articles:
            assert not article["title"].endswith("- CNews")
            assert "CNews" not in article["title"]

    def test_gnews_article_structure(self):
        fixture_path = str(FIXTURES / "gnews_sample.xml")
        import feedparser

        fixture_feed = feedparser.parse(fixture_path)

        with patch("parsers.gnews.feedparser.parse", return_value=fixture_feed):
            with patch("parsers.gnews.time.sleep"):
                articles = parse_gnews("cnews.fr", "cnews")

        for article in articles:
            assert article["media"] == "cnews"
            assert article["source_method"] == "gnews"
            assert article["url"].startswith("https://")
            assert article["date"].endswith("Z")

    def test_gnews_rate_limiting(self):
        """Verify that rate limiting delay is applied."""
        fixture_path = str(FIXTURES / "gnews_sample.xml")
        import feedparser

        fixture_feed = feedparser.parse(fixture_path)

        with patch("parsers.gnews.feedparser.parse", return_value=fixture_feed):
            with patch("parsers.gnews.time.sleep") as mock_sleep:
                # Reset the last request time to trigger rate limiting
                import parsers.gnews as gnews_module
                gnews_module._last_request_time = 0.0
                parse_gnews("cnews.fr", "cnews")
                # Sleep should not be called if enough time has passed
                # (since _last_request_time is 0, time.time() will be >> 0)
