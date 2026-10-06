import pytest

from kiosque_pipeline import layers
from kiosque_pipeline.metrics import blind_spot, day_kpis, hhi, owner_key, run, story_metrics
from conftest import RUN_DATE, SOURCES

MAJORS = {"bollore", "niel", "bouygues", "arnault", "kretinsky", "saade"}
BY_SLUG = {s["slug"]: s for s in SOURCES}


def art(media, owner, url=None):
    return {"media": media, "title": f"titre {media}", "url": url or f"https://{media}.fr/x",
            "date": None, "owner_group": owner, "influence": None}


class TestHhi:
    def test_monopoly(self):
        assert hhi({"bollore": 3}) == 10000.0

    def test_even_split(self):
        assert hhi({"bollore": 1, "niel": 1}) == 5000.0
        assert hhi({"a": 1, "b": 1, "c": 1}) == 3333.3

    def test_empty(self):
        assert hhi({}) == 0.0


def test_owner_key_splits_independents_only():
    assert owner_key("independant", "mediapart") == "independant:mediapart"
    assert owner_key("public", "franceinfo") == "public"


class TestBlindSpot:
    def test_single_major_group(self):
        assert blind_spot({"bollore": 2}, 2, MAJORS) == "single_group"

    def test_single_public_group(self):
        assert blind_spot({"public": 2}, 2, MAJORS) == "single_group"

    def test_two_independents_is_not_a_blind_spot(self):
        assert blind_spot({"independant": 2}, 2, MAJORS) is None

    def test_ignored_by_majors_needs_three_media(self):
        assert blind_spot({"independant": 2, "public": 1}, 3, MAJORS) == "ignored_by_majors"
        assert blind_spot({"independant": 1, "public": 1}, 2, MAJORS) is None

    def test_mixed_with_major_is_none(self):
        assert blind_spot({"bollore": 1, "independant": 2}, 3, MAJORS) is None


class TestStoryMetrics:
    def test_counts_distinct_media_not_articles(self):
        story = {"id": f"{RUN_DATE}-001", "title": "t", "articles": [
            art("cnews", "bollore", "https://cnews.fr/1"), art("cnews", "bollore", "https://cnews.fr/2"),
            art("cnews", "bollore", "https://cnews.fr/3"), art("le-monde", "niel"),
        ]}
        m = story_metrics(story, MAJORS)
        assert m["article_count"] == 4
        assert m["media_count"] == 2
        assert m["groups"] == {"bollore": 1, "niel": 1}
        assert m["hhi"] == 5000.0
        assert m["dominant_group"] == "bollore"  # alphabetical tie-break
        assert m["dominant_share"] == 50.0
        assert m["blind_spot"] is None

    def test_independents_lower_hhi_but_aggregate_in_groups(self):
        story = {"id": "s", "title": "t", "articles": [
            art("mediapart", "independant"), art("reporterre", "independant"), art("blast", "independant"),
        ]}
        m = story_metrics(story, MAJORS)
        assert m["groups"] == {"independant": 3}
        assert m["hhi"] == 3333.3
        assert m["dominant_share"] == 100.0
        assert m["blind_spot"] == "ignored_by_majors"


def test_day_kpis():
    stories = [{"hhi": 5000.0, "blind_spot": None}, {"hhi": 10000.0, "blind_spot": "single_group"},
               {"hhi": 2000.0, "blind_spot": None}]
    articles = [{"media": "cnews"}, {"media": "cnews"}, {"media": "le-monde"}, {"media": "mediapart"}]
    k = day_kpis(stories, articles, BY_SLUG)
    assert k == {"articles": 4, "media": 3, "stories": 3, "blind_spots": 1, "median_hhi": 5000.0,
                 "group_article_share": {"bollore": 50.0, "independant": 25.0, "niel": 25.0}}


def test_day_kpis_empty_day():
    assert day_kpis([], [], BY_SLUG)["median_hhi"] is None


def test_run_writes_gold(ctx):
    ctx.storage.write_json(layers.bronze_articles(RUN_DATE), {
        "articles": [{"media": "cnews"}, {"media": "le-monde"}],
        "collection": {"total_sources": 2, "success_count": 2, "failed": []},
    })
    ctx.storage.write_json(layers.silver_enriched(RUN_DATE), {"stories": [
        {"id": f"{RUN_DATE}-001", "title": "t", "articles": [art("cnews", "bollore"), art("le-monde", "niel")]},
    ]})
    assert run(ctx) == {"stories": 1, "blind_spots": 0}
    gold = ctx.storage.read_json(layers.gold_metrics(RUN_DATE))
    assert gold["kpis"]["stories"] == 1
    assert gold["collection"]["success_count"] == 2
