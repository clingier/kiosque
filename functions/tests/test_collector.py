"""Tests for collector.py — Collection orchestration, retry, and reporting."""

import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock, call

import pytest

# Add functions/ to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from collector import (
    load_sources,
    _collect_one_sync,
    _try_feed_with_retry,
    build_report,
    run_collection,
)
from storage import StorageWriter


# ──────────────────────────────────────────────────────────────────────
# Test load_sources
# ──────────────────────────────────────────────────────────────────────


class TestLoadSources:
    def test_loads_sources_yaml(self):
        config_path = str(
            Path(__file__).parent.parent.parent / "config" / "sources.yaml"
        )
        sources = load_sources(config_path)

        assert len(sources) == 65
        slugs = [s["slug"] for s in sources]
        assert len(slugs) == len(set(slugs)), "Slugs must be unique"

    def test_all_required_fields_present(self):
        config_path = str(
            Path(__file__).parent.parent.parent / "config" / "sources.yaml"
        )
        sources = load_sources(config_path)

        valid_owner_groups = {
            "bollore", "niel", "bouygues", "arnault",
            "kretinsky", "saade", "public", "independant",
        }

        for source in sources:
            assert "slug" in source, f"Missing slug in {source}"
            assert "name" in source, f"Missing name in {source}"
            assert "owner_group" in source, f"Missing owner_group in {source.get('slug', '?')}"
            assert source["owner_group"] in valid_owner_groups, (
                f"Invalid owner_group '{source['owner_group']}' for {source['slug']}"
            )
            assert "feeds" in source, f"Missing feeds in {source['slug']}"

    def test_media_without_feeds_have_fallback(self):
        config_path = str(
            Path(__file__).parent.parent.parent / "config" / "sources.yaml"
        )
        sources = load_sources(config_path)

        for source in sources:
            feeds = source.get("feeds", [])
            fallback = source.get("fallback_domain", "")
            if not feeds:
                assert fallback, (
                    f"{source['slug']} has no feeds and no fallback_domain"
                )

    def test_nonexistent_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_sources("/nonexistent/sources.yaml")


# ──────────────────────────────────────────────────────────────────────
# Test _collect_one_sync (hierarchy logic)
# ──────────────────────────────────────────────────────────────────────


class TestCollectOneSync:
    def test_first_successful_feed_wins(self):
        """The first feed that returns articles should be used."""
        source = {
            "slug": "test-media",
            "name": "Test Media",
            "feeds": [
                {"url": "http://test.fr/rss1.xml", "type": "rss"},
                {"url": "http://test.fr/sitemap.xml", "type": "sitemap"},
            ],
            "fallback_domain": "test.fr",
        }

        mock_articles = [
            {"media": "test-media", "title": "Article 1", "url": "http://test.fr/1", "date": "2026-07-03T08:00:00Z", "source_method": "rss"}
        ]

        with patch("collector.parse_rss", return_value=mock_articles) as mock_rss:
            with patch("collector.parse_sitemap") as mock_sitemap:
                result = _collect_one_sync(source)

        assert result["status"] == "ok"
        assert result["source_method"] == "rss"
        assert result["article_count"] == 1
        # Sitemap should not have been called
        mock_sitemap.assert_not_called()

    def test_fallback_to_gnews(self):
        """If all native feeds fail, gnews fallback should be tried."""
        source = {
            "slug": "test-media",
            "name": "Test Media",
            "feeds": [
                {"url": "http://test.fr/rss.xml", "type": "rss"},
            ],
            "fallback_domain": "test.fr",
        }

        mock_gnews_articles = [
            {"media": "test-media", "title": "GNews Article", "url": "http://test.fr/g1", "date": "2026-07-03T08:00:00Z", "source_method": "gnews"}
        ]

        with patch("collector.parse_rss", return_value=[]):
            with patch("collector.parse_gnews", return_value=mock_gnews_articles):
                with patch("collector.time.sleep"):  # Skip retry delays
                    result = _collect_one_sync(source)

        assert result["status"] == "ok"
        assert result["source_method"] == "gnews"

    def test_all_fail_returns_error(self):
        """If everything fails, return an error result."""
        source = {
            "slug": "test-media",
            "name": "Test Media",
            "feeds": [
                {"url": "http://test.fr/rss.xml", "type": "rss"},
            ],
            "fallback_domain": "test.fr",
        }

        with patch("collector.parse_rss", return_value=[]):
            with patch("collector.parse_gnews", return_value=[]):
                with patch("collector.time.sleep"):
                    result = _collect_one_sync(source)

        assert result["status"] == "error"
        assert result["article_count"] == 0

    def test_no_feeds_no_fallback(self):
        """A source with no feeds and no fallback should error immediately."""
        source = {
            "slug": "no-feeds",
            "name": "No Feeds Media",
            "feeds": [],
            "fallback_domain": "",
        }

        result = _collect_one_sync(source)
        assert result["status"] == "error"


# ──────────────────────────────────────────────────────────────────────
# Test retry logic
# ──────────────────────────────────────────────────────────────────────


class TestRetryLogic:
    def test_retries_on_empty_result(self):
        """Parser returning [] should trigger retries."""
        with patch("collector.parse_rss", return_value=[]) as mock_parse:
            with patch("collector.time.sleep"):
                result = _try_feed_with_retry("http://test.fr/rss.xml", "rss", "test")

        assert result == []
        assert mock_parse.call_count == 3  # MAX_RETRIES

    def test_retries_on_exception(self):
        """Exceptions should trigger retries with backoff."""
        with patch("collector.parse_rss", side_effect=Exception("Network error")) as mock_parse:
            with patch("collector.time.sleep") as mock_sleep:
                result = _try_feed_with_retry("http://test.fr/rss.xml", "rss", "test")

        assert result == []
        assert mock_parse.call_count == 3
        # Backoff: 1s, 2s
        assert mock_sleep.call_count == 2

    def test_success_on_second_attempt(self):
        """If the first attempt fails but the second succeeds, use it."""
        mock_articles = [{"media": "test", "title": "OK", "url": "http://t.fr/1", "date": "2026-07-03T08:00:00Z", "source_method": "rss"}]

        with patch("collector.parse_rss", side_effect=[[], mock_articles]):
            with patch("collector.time.sleep"):
                result = _try_feed_with_retry("http://test.fr/rss.xml", "rss", "test")

        assert len(result) == 1
        assert result[0]["title"] == "OK"


# ──────────────────────────────────────────────────────────────────────
# Test build_report
# ──────────────────────────────────────────────────────────────────────


class TestBuildReport:
    def test_report_structure(self):
        results = [
            {"slug": "media-1", "status": "ok", "source_method": "rss", "article_count": 10, "duration_ms": 200},
            {"slug": "media-2", "status": "ok", "source_method": "sitemap", "article_count": 5, "duration_ms": 300},
            {"slug": "media-3", "status": "error", "error": "HTTP 403", "source_method": "rss", "article_count": 0, "duration_ms": 4000, "attempts": 3},
        ]

        started = datetime(2026, 7, 3, 6, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2026, 7, 3, 6, 3, 0, tzinfo=timezone.utc)

        report = build_report(results, started, finished)

        assert report["date"] == "2026-07-03"
        assert report["total_sources"] == 3
        assert report["success_count"] == 2
        assert report["failure_count"] == 1
        assert report["total_articles"] == 15
        assert report["duration_seconds"] == 180
        assert len(report["sources"]) == 3

    def test_report_contains_error_details(self):
        results = [
            {"slug": "failing", "status": "error", "error": "Timeout", "source_method": "rss", "article_count": 0, "duration_ms": 15000, "attempts": 3},
        ]

        started = datetime(2026, 7, 3, 6, 0, 0, tzinfo=timezone.utc)
        finished = datetime(2026, 7, 3, 6, 0, 15, tzinfo=timezone.utc)

        report = build_report(results, started, finished)

        error_source = report["sources"][0]
        assert error_source["status"] == "error"
        assert error_source["error"] == "Timeout"
        assert error_source["attempts"] == 3


# ──────────────────────────────────────────────────────────────────────
# Test run_collection (end-to-end with mock storage)
# ──────────────────────────────────────────────────────────────────────


class TestRunCollection:
    def test_writes_report_always(self):
        """The _report.json should always be written, even if everything fails."""
        mock_sources = [
            {"slug": "test-1", "name": "Test 1", "feeds": [], "fallback_domain": ""},
            {"slug": "test-2", "name": "Test 2", "feeds": [], "fallback_domain": ""},
        ]

        mock_writer = MagicMock(spec=StorageWriter)

        with patch("collector.load_sources", return_value=mock_sources):
            with patch("collector.time.sleep"):
                report = run_collection(writer=mock_writer)

        # Report should be written even though both sources failed
        write_calls = mock_writer.write.call_args_list
        report_calls = [c for c in write_calls if "_report.json" in c[0][0]]
        assert len(report_calls) == 1

    def test_high_failure_rate_logged(self):
        """If >5 sources fail, an error should be logged."""
        mock_sources = [
            {"slug": f"test-{i}", "name": f"Test {i}", "feeds": [], "fallback_domain": ""}
            for i in range(10)
        ]

        mock_writer = MagicMock(spec=StorageWriter)

        with patch("collector.load_sources", return_value=mock_sources):
            with patch("collector.time.sleep"):
                with patch("collector.logger") as mock_logger:
                    report = run_collection(writer=mock_writer)

        # Should log an error about high failure rate
        error_calls = [
            c for c in mock_logger.error.call_args_list
            if "FAILURE" in str(c).upper() or "failure" in str(c).lower()
        ]
        assert len(error_calls) >= 1

    def test_successful_sources_written(self):
        """Successful sources should have their JSON files written."""
        mock_sources = [
            {
                "slug": "test-ok",
                "name": "Test OK",
                "feeds": [{"url": "http://test.fr/rss.xml", "type": "rss"}],
                "fallback_domain": "test.fr",
            },
        ]

        mock_articles = [
            {"media": "test-ok", "title": "Article", "url": "http://test.fr/1", "date": "2026-07-03T08:00:00Z", "source_method": "rss"}
        ]

        mock_writer = MagicMock(spec=StorageWriter)

        with patch("collector.load_sources", return_value=mock_sources):
            with patch("collector.parse_rss", return_value=mock_articles):
                report = run_collection(writer=mock_writer)

        # Should have written test-ok.json and _report.json
        write_calls = mock_writer.write.call_args_list
        paths_written = [c[0][0] for c in write_calls]
        assert any("test-ok.json" in p for p in paths_written)
        assert any("_report.json" in p for p in paths_written)
