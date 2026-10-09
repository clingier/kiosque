import pytest

from kiosque_pipeline.metrics import day_kpis, story_metrics
from kiosque_pipeline.steps import metrics, ref
from spark_seed import seed_bronze, seed_story_articles
from conftest import RUN_DATE, SOURCES

pytestmark = pytest.mark.spark
MAJORS = {"bollore", "niel", "bouygues", "arnault", "kretinsky", "saade"}
OWNER = {s["slug"]: s["owner_group"] for s in SOURCES}


def x(media, n=0):
    return {"media": media, "title": f"titre {media} {n}", "url": f"https://{media}.fr/{n}",
            "date": None, "owner_group": OWNER[media], "influence": None}


STORIES = [
    {"id": f"{RUN_DATE}-001", "title": "Égalité bolloré niel", "articles": [x("cnews", 1), x("cnews", 2), x("cnews", 3), x("le-monde")]},
    {"id": f"{RUN_DATE}-002", "title": "Trois indépendants", "articles": [x("mediapart"), x("reporterre"), x("blast")]},
    {"id": f"{RUN_DATE}-003", "title": "Seul Bolloré", "articles": [x("cnews"), x("europe-1")]},
    {"id": f"{RUN_DATE}-004", "title": "Public et indépendants", "articles": [x("franceinfo"), x("mediapart"), x("reporterre")]},
]
BRONZE = [{"id": f"b{i}", "media": m, "title": "t un deux trois", "url": f"https://{m}.fr/b{i}", "date": None}
          for i, m in enumerate(["cnews", "cnews", "le-monde", "mediapart"])]


def seed(ctx, stories=STORIES):
    ref.run(ctx)
    seed_bronze(ctx, BRONZE)
    seed_story_articles(ctx, stories)


def test_story_metrics_match_reference(sctx):
    seed(sctx)
    assert metrics.run(sctx) == {"stories": 4, "blind_spots": 3}
    got = {r.story_id: r for r in sctx.spark.table("spark_catalog.gold.story_metrics").collect()}
    for story in STORIES:
        want = story_metrics(story, MAJORS)
        row = got[story["id"]]
        assert row.title == story["title"]
        assert (row.article_count, row.media_count, row.hhi, row.dominant_group, row.dominant_share, row.blind_spot) == (
            want["article_count"], want["media_count"], want["hhi"], want["dominant_group"], want["dominant_share"], want["blind_spot"])
        assert dict(row.groups) == want["groups"]


def test_day_kpis_match_reference_with_even_story_count(sctx):
    seed(sctx)
    metrics.run(sctx)
    [row] = sctx.spark.table("spark_catalog.gold.day_kpis").collect()
    want = day_kpis([story_metrics(s, MAJORS) for s in STORIES], BRONZE, {s["slug"]: s for s in SOURCES})
    assert (row.articles, row.media, row.stories, row.blind_spots) == (want["articles"], want["media"], want["stories"], want["blind_spots"])
    assert row.median_hhi == pytest.approx(want["median_hhi"])
    assert dict(row.group_article_share) == want["group_article_share"]


def test_empty_day_has_one_kpi_row(sctx):
    ref.run(sctx)
    seed_bronze(sctx, [])
    seed_story_articles(sctx, [])
    assert metrics.run(sctx) == {"stories": 0, "blind_spots": 0}
    [row] = sctx.spark.table("spark_catalog.gold.day_kpis").collect()
    assert (row.articles, row.stories, row.median_hhi, dict(row.group_article_share)) == (0, 0, None, {})
