"""Tests for parsers/rss.py — RSS/Atom feed parser."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add functions/ to the path so we can import parsers
sys.path.insert(0, str(Path(__file__).parent.parent))

from parsers.rss import parse_rss, _clean_title, _parse_date

FIXTURES = Path(__file__).parent / "fixtures"

# Fixtures have dates around July 3 2026 — freeze "now" so freshness filter works
FIXTURE_NOW = datetime(2026, 7, 3, 8, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _freeze_rss_time():
    """Set a very large freshness window so fixture dates always count as fresh."""
    with patch("parsers.rss.FRESHNESS_WINDOW_HOURS", 999999):
        yield


# ──────────────────────────────────────────────────────────────────────
# Unit tests for _clean_title
# ──────────────────────────────────────────────────────────────────────


class TestCleanTitle:
    def test_plain_text(self):
        assert _clean_title("Simple title") == "Simple title"

    def test_html_tags_stripped(self):
        assert _clean_title("Title with <b>bold</b> text") == "Title with bold text"
        assert _clean_title("<em>Emphasis</em> here") == "Emphasis here"

    def test_cdata_unwrapped(self):
        assert _clean_title("<![CDATA[Title inside CDATA]]>") == "Title inside CDATA"

    def test_cdata_with_html(self):
        result = _clean_title("<![CDATA[Title with <b>bold</b>]]>")
        assert result == "Title with bold"

    def test_html_entities_decoded(self):
        assert _clean_title("L&#39;art de vivre") == "L'art de vivre"
        assert _clean_title("Rock &amp; Roll") == "Rock & Roll"
        assert _clean_title("Prix &lt; 10€") == "Prix < 10€"

    def test_whitespace_normalised(self):
        assert _clean_title("  Too   many   spaces  ") == "Too many spaces"
        assert _clean_title("\n\tTabbed\n\ttitle\n") == "Tabbed title"

    def test_empty_string(self):
        assert _clean_title("") == ""

    def test_none_returns_empty(self):
        assert _clean_title(None) == ""


# ──────────────────────────────────────────────────────────────────────
# Integration tests with fixtures (feedparser on local XML files)
# ──────────────────────────────────────────────────────────────────────


class TestParseRssStandard:
    """Test with a standard RSS 2.0 fixture (Le Monde style)."""

    def test_parses_fresh_articles(self):
        fixture_path = str(FIXTURES / "rss_standard.xml")
        # Override autouse large window + freeze now to fixture date
        with patch("parsers.rss.FRESHNESS_WINDOW_HOURS", 48), \
             patch("parsers.rss.datetime", wraps=datetime) as mock_dt:
            mock_dt.now.return_value = FIXTURE_NOW
            articles = parse_rss(fixture_path, "le-monde")

        # Should have 3 fresh articles (4th is > 48h old)
        assert len(articles) == 3

    def test_article_structure(self):
        fixture_path = str(FIXTURES / "rss_standard.xml")
        articles = parse_rss(fixture_path, "le-monde")

        for article in articles:
            assert "media" in article
            assert "title" in article
            assert "url" in article
            assert "date" in article
            assert "source_method" in article
            assert article["media"] == "le-monde"
            assert article["source_method"] == "rss"
            assert article["url"].startswith("https://")

    def test_filters_old_articles(self):
        fixture_path = str(FIXTURES / "rss_standard.xml")
        with patch("parsers.rss.FRESHNESS_WINDOW_HOURS", 48), \
             patch("parsers.rss.datetime", wraps=datetime) as mock_dt:
            mock_dt.now.return_value = FIXTURE_NOW
            articles = parse_rss(fixture_path, "le-monde")

        # The old article (Jun 01) should be filtered out
        urls = [a["url"] for a in articles]
        assert not any("vieux" in url or "999999" in url for url in urls)

    def test_dates_are_utc_iso8601(self):
        fixture_path = str(FIXTURES / "rss_standard.xml")
        articles = parse_rss(fixture_path, "le-monde")

        for article in articles:
            assert article["date"].endswith("Z")
            # Should parse without error
            datetime.fromisoformat(article["date"].replace("Z", "+00:00"))


class TestParseRssAtom:
    """Test with an Atom feed fixture."""

    def test_parses_atom_entries(self):
        fixture_path = str(FIXTURES / "rss_atom.xml")
        articles = parse_rss(fixture_path, "france-info")

        assert len(articles) == 2
        assert all(a["source_method"] == "rss" for a in articles)

    def test_atom_titles_extracted(self):
        fixture_path = str(FIXTURES / "rss_atom.xml")
        articles = parse_rss(fixture_path, "france-info")

        titles = [a["title"] for a in articles]
        assert any("retraites" in t.lower() for t in titles)
        assert any("tour de france" in t.lower() for t in titles)


class TestParseRssCdata:
    """Test with CDATA-wrapped titles."""

    def test_cdata_titles_cleaned(self):
        fixture_path = str(FIXTURES / "rss_cdata.xml")
        articles = parse_rss(fixture_path, "le-figaro")

        assert len(articles) == 3

        # HTML tags inside CDATA should be stripped
        titles = [a["title"] for a in articles]
        assert not any("<b>" in t for t in titles)
        assert not any("<![CDATA[" in t for t in titles)

    def test_nested_entities_decoded(self):
        fixture_path = str(FIXTURES / "rss_cdata.xml")
        articles = parse_rss(fixture_path, "le-figaro")

        # The title "L&#39;art de vivre" should become "L'art de vivre"
        titles = [a["title"] for a in articles]
        culture_titles = [t for t in titles if "vivre" in t.lower()]
        assert len(culture_titles) == 1
        assert "&#39;" not in culture_titles[0]


class TestParseRssNoTimezone:
    """Test with dates missing timezone info."""

    def test_naive_dates_handled(self):
        fixture_path = str(FIXTURES / "rss_no_timezone.xml")
        articles = parse_rss(fixture_path, "ouest-france")

        assert len(articles) >= 1

        for article in articles:
            # Dates should be normalised to UTC ISO 8601
            assert article["date"].endswith("Z")


class TestParseRssEmpty:
    """Test with an empty RSS feed."""

    def test_empty_feed_returns_empty_list(self):
        fixture_path = str(FIXTURES / "rss_empty.xml")
        articles = parse_rss(fixture_path, "empty-media")
        assert articles == []


class TestParseRssErrorHandling:
    """Test error handling for inaccessible or invalid feeds."""

    def test_nonexistent_file_returns_empty(self):
        articles = parse_rss("/nonexistent/path/feed.xml", "test-media")
        assert articles == []

    def test_deduplication_by_url(self):
        """Verify that duplicate URLs within a feed are deduplicated."""
        fixture_path = str(FIXTURES / "rss_standard.xml")
        articles = parse_rss(fixture_path, "test-dedup")
        urls = [a["url"] for a in articles]
        assert len(urls) == len(set(urls))
