import pytest

from kiosque_pipeline.ownership import enrich
from kiosque_pipeline.steps import ownership, ref
from spark_seed import TS, seed_bronze, seed_stories
from conftest import RUN_DATE, SOURCES

pytestmark = pytest.mark.spark

ARTICLES = [
    {"id": "a1", "media": "cnews", "title": "T1 un deux trois", "url": "https://cnews.fr/1", "date": "2026-10-05T20:00:00Z", "source_method": "rss"},
    {"id": "a2", "media": "valeurs-actuelles", "title": "T2 un deux trois", "url": "https://va.fr/2", "date": "2026-10-05T19:00:00Z", "source_method": "rss"},
    {"id": "a3", "media": "le-monde", "title": "T3 un deux trois", "url": "https://lemonde.fr/3", "date": None, "source_method": "rss"},
]
STORIES = [{"id": f"{RUN_DATE}-001", "title": "T1 un deux trois", "article_ids": ["a1", "a2", "a3"]}]


def test_matches_reference_implementation(sctx):
    from pyspark.sql import functions as F

    ref.run(sctx)
    seed_bronze(sctx, ARTICLES)
    seed_stories(sctx, STORIES)
    assert ownership.run(sctx) == {"stories": 1}

    got = sorted(
        (r.story_id, r.media, r.title, r.url, r.date, r.owner_group, r.influence)
        for r in sctx.spark.table("spark_catalog.silver.story_articles")
        .select("story_id", "media", "title", "url", F.date_format("date", TS).alias("date"), "owner_group", "influence")
        .collect()
    )
    [story] = enrich(STORIES, ARTICLES, {s["slug"]: s for s in SOURCES})
    expected = sorted((story["id"], x["media"], x["title"], x["url"], x["date"], x["owner_group"], x["influence"]) for x in story["articles"])
    assert got == expected


def test_rerun_replaces_day(sctx):
    ref.run(sctx)
    seed_bronze(sctx, ARTICLES)
    seed_stories(sctx, STORIES)
    ownership.run(sctx)
    ownership.run(sctx)
    assert sctx.spark.table("spark_catalog.silver.story_articles").count() == 3
