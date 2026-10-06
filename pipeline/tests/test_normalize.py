from datetime import datetime, timezone

import pytest

from kiosque_pipeline import layers
from kiosque_pipeline.normalize import (
    RawDataMissing, canonical_url, clean_title, normalize_articles, run,
)
from conftest import RUN_DATE

REF = datetime(2026, 10, 6, 6, 4, 0, tzinfo=timezone.utc)


def raw(media, articles, method="rss"):
    return {"media": media, "collected_at": "2026-10-06T06:04:00Z", "source_method": method,
            "feed_url": "", "article_count": len(articles), "articles": articles}


def art(title, url, date="2026-10-05T18:00:00Z"):
    return {"title": title, "url": url, "date": date}


class TestCanonicalUrl:
    def test_strips_tracking_params_and_fragment(self):
        assert canonical_url("HTTPS://WWW.LeMonde.fr/politique/article.html?utm_source=rss&xtor=RSS-3208&page=2#comments") \
            == "https://www.lemonde.fr/politique/article.html?page=2"

    def test_strips_trailing_slash_except_root(self):
        assert canonical_url("https://reporterre.net/climat/") == "https://reporterre.net/climat"
        assert canonical_url("https://reporterre.net/") == "https://reporterre.net/"


class TestCleanTitle:
    def test_unescapes_and_normalizes_whitespace(self):
        assert clean_title("  Retraites&nbsp;:  l&#39;Assemblée   vote ") == "Retraites : l'Assemblée vote"


class TestNormalizeArticles:
    def test_dedupes_tracking_variants(self):
        files = [
            raw("le-monde", [art("Le gouvernement présente son budget 2027", "https://www.lemonde.fr/a.html?utm_source=x", "2026-10-05T20:00:00Z")]),
            raw("le-monde", [art("Le gouvernement présente son budget 2027", "https://www.lemonde.fr/a.html#top", "2026-10-05T19:00:00Z")]),
        ]
        out = normalize_articles(files, REF, {"le-monde"})
        assert len(out) == 1
        assert out[0]["url"] == "https://www.lemonde.fr/a.html"
        assert out[0]["date"] == "2026-10-05T19:00:00Z"  # earliest kept

    def test_window_drops_old_and_far_future(self):
        files = [raw("cnews", [
            art("Article bien dans la fenêtre du jour", "https://cnews.fr/1", "2026-10-05T07:00:00Z"),
            art("Article trop ancien pour la journée", "https://cnews.fr/2", "2026-10-05T05:00:00Z"),
            art("Article daté dans un futur lointain", "https://cnews.fr/3", "2026-10-06T09:00:00Z"),
            art("Article sans aucune date de publication", "https://cnews.fr/4", None),
        ])]
        urls = {a["url"] for a in normalize_articles(files, REF, {"cnews"})}
        assert urls == {"https://cnews.fr/1", "https://cnews.fr/4"}

    def test_drops_short_titles_and_unknown_media(self):
        files = [
            raw("cnews", [art("Direct", "https://cnews.fr/live")]),
            raw("unknown-media", [art("Un titre parfaitement valable ici", "https://x.fr/1")]),
        ]
        assert normalize_articles(files, REF, {"cnews"}) == []

    def test_output_shape_and_order(self):
        files = [
            raw("le-monde", [art("Budget : ce que contient le projet", "https://www.lemonde.fr/b")]),
            raw("cnews", [art("Budget : les principales mesures dévoilées", "https://www.cnews.fr/a")], method="gnews"),
        ]
        out = normalize_articles(files, REF, {"cnews", "le-monde"})
        assert [a["media"] for a in out] == ["cnews", "le-monde"]
        assert set(out[0]) == {"id", "media", "title", "url", "date", "source_method"}
        assert out[0]["source_method"] == "gnews"
        assert len(out[0]["id"]) == 16


class TestRun:
    def _write_report(self, ctx, failed=()):
        ctx.storage.write_json(layers.raw_report(RUN_DATE), {
            "finished_at": "2026-10-06T06:04:00Z", "total_sources": 3, "success_count": 3 - len(failed),
            "sources": [{"slug": s, "status": "error"} for s in failed] + [{"slug": "cnews", "status": "ok"}],
        })

    def test_missing_report_raises(self, ctx):
        with pytest.raises(RawDataMissing):
            run(ctx)

    def test_empty_day(self, ctx):
        self._write_report(ctx, failed=("le-monde", "tf1-info"))
        assert run(ctx) == {"articles": 0}
        bronze = ctx.storage.read_json(layers.bronze_articles(RUN_DATE))
        assert bronze["articles"] == []
        assert bronze["collection"] == {"total_sources": 3, "success_count": 1, "failed": ["le-monde", "tf1-info"]}

    def test_reads_raw_files_and_writes_bronze(self, ctx):
        self._write_report(ctx)
        ctx.storage.write_json(f"{layers.raw_dir(RUN_DATE)}/cnews.json",
                               raw("cnews", [art("Budget : les principales mesures dévoilées", "https://www.cnews.fr/a")]))
        assert run(ctx) == {"articles": 1}
        bronze = ctx.storage.read_json(layers.bronze_articles(RUN_DATE))
        assert bronze["run_date"] == RUN_DATE
        assert bronze["reference_time"] == "2026-10-06T06:04:00Z"
        assert bronze["articles"][0]["media"] == "cnews"
