from datetime import datetime, timezone

from kiosque_pipeline.normalize import (
    canonical_url, clean_title, normalize_articles,
)

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

    def test_drops_non_http_urls(self):
        files = [raw("cnews", [
            art("Un titre parfaitement valable ici", "javascript:void(0)"),
            art("Un autre titre tout à fait valable", "/relative/path"),
            art("Un troisième titre bien valable aussi", "https://www.cnews.fr/ok"),
        ])]
        assert [a["url"] for a in normalize_articles(files, REF, {"cnews"})] == ["https://www.cnews.fr/ok"]

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
