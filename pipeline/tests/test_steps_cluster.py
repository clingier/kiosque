import pytest

from fakes import FakeEmbedder
from kiosque_pipeline.cluster import build_stories, cluster_labels
from kiosque_pipeline.steps import cluster
from spark_seed import seed_bronze
from conftest import RUN_DATE

pytestmark = pytest.mark.spark


def a(i, media, title):
    return {"id": f"id{i}", "media": media, "title": title, "url": f"https://x.fr/{i}", "date": None, "source_method": "rss"}


ARTICLES = [
    a(1, "cnews", "Retraites : le vote reporté à l'Assemblée"),
    a(2, "le-monde", "Retraites : pourquoi le vote est reporté"),
    a(3, "franceinfo", "Le vote sur les retraites repoussé"),
    a(4, "reporterre", "Climat : record de chaleur en octobre"),
    a(5, "mediapart", "Climat : octobre le plus chaud jamais mesuré"),
    a(6, "cnews", "Climat : la chaleur bat des records"),
    a(7, "cnews", "Un fait divers isolé en Bretagne ce matin"),
    a(8, "tf1-info", "Retraites : le vote reporté, la majorité divisée"),
]


def story_rows(ctx):
    return sorted((r.story_id, r.title, r.article_id) for r in ctx.spark.table("spark_catalog.silver.stories").collect())


def test_matches_reference_implementation(sctx):
    seed_bronze(sctx, ARTICLES)
    assert cluster.run(sctx, FakeEmbedder, 0.4) == {"stories": 2}

    ordered = sorted(ARTICLES, key=lambda x: (x["media"], x["url"]))
    emb = FakeEmbedder().encode([x["title"] for x in ordered])
    expected = sorted(
        (s["id"], s["title"], aid)
        for s in build_stories(RUN_DATE, ordered, cluster_labels(emb, 0.4), emb)
        for aid in s["article_ids"]
    )
    assert story_rows(sctx) == expected


def test_rerun_gives_identical_rows(sctx):
    seed_bronze(sctx, ARTICLES)
    cluster.run(sctx, FakeEmbedder, 0.4)
    first = story_rows(sctx)
    cluster.run(sctx, FakeEmbedder, 0.4)
    assert story_rows(sctx) == first


def test_empty_day(sctx):
    seed_bronze(sctx, [])
    assert cluster.run(sctx, FakeEmbedder, 0.4) == {"stories": 0}
    assert story_rows(sctx) == []
