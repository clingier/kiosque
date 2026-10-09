import pytest

from kiosque_pipeline.ownership import enrich
from conftest import RUN_DATE, SOURCES

BY_SLUG = {s["slug"]: s for s in SOURCES}
ARTICLES = [
    {"id": "a1", "media": "cnews", "title": "T1 un deux trois", "url": "https://cnews.fr/1", "date": "2026-10-05T20:00:00Z", "source_method": "rss"},
    {"id": "a2", "media": "valeurs-actuelles", "title": "T2 un deux trois", "url": "https://va.fr/2", "date": "2026-10-05T19:00:00Z", "source_method": "rss"},
]
STORIES = [{"id": f"{RUN_DATE}-001", "title": "T1 un deux trois", "article_ids": ["a1", "a2"]}]


def test_enrich_attaches_owner_and_influence():
    [story] = enrich(STORIES, ARTICLES, BY_SLUG)
    assert story["id"] == f"{RUN_DATE}-001"
    assert [x["media"] for x in story["articles"]] == ["valeurs-actuelles", "cnews"]  # by date
    assert story["articles"][1] == {
        "media": "cnews", "title": "T1 un deux trois", "url": "https://cnews.fr/1",
        "date": "2026-10-05T20:00:00Z", "owner_group": "bollore", "influence": None,
    }
    assert story["articles"][0]["influence"] == "sterin-pericles"


def test_enrich_unknown_article_id_raises():
    with pytest.raises(KeyError):
        enrich([{"id": "s", "title": "t", "article_ids": ["missing"]}], ARTICLES, BY_SLUG)
