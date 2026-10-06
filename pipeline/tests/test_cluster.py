import numpy as np

from kiosque_pipeline import layers
from kiosque_pipeline.cluster import build_stories, cluster_labels, run
from conftest import RUN_DATE
from fakes import FakeEmbedder

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


def test_cluster_labels_groups_close_vectors():
    emb = FakeEmbedder().encode([x["title"] for x in ARTICLES])
    labels = cluster_labels(emb, 0.4)
    assert labels[0] == labels[1] == labels[2] == labels[7]
    assert labels[3] == labels[4] == labels[5]
    assert len({labels[0], labels[3], labels[6]}) == 3


def test_cluster_labels_handles_tiny_input():
    assert cluster_labels(np.zeros((0, 3)), 0.4) == []
    assert cluster_labels(np.array([[1.0, 0.0]]), 0.4) == [0]


def test_build_stories_ranks_and_drops_single_media_clusters():
    emb = FakeEmbedder().encode([x["title"] for x in ARTICLES])
    stories = build_stories(RUN_DATE, ARTICLES, cluster_labels(emb, 0.4), emb)
    assert [s["id"] for s in stories] == [f"{RUN_DATE}-001", f"{RUN_DATE}-002"]
    assert sorted(stories[0]["article_ids"]) == ["id1", "id2", "id3", "id8"]  # 4 media ranks first
    assert sorted(stories[1]["article_ids"]) == ["id4", "id5", "id6"]
    assert all("id7" not in s["article_ids"] for s in stories)


def test_story_ids_deterministic():
    emb = FakeEmbedder().encode([x["title"] for x in ARTICLES])
    labels = cluster_labels(emb, 0.4)
    assert build_stories(RUN_DATE, ARTICLES, labels, emb) == build_stories(RUN_DATE, ARTICLES, labels, emb)


def test_run_writes_silver(ctx):
    ctx.storage.write_json(layers.bronze_articles(RUN_DATE), {"run_date": RUN_DATE, "articles": ARTICLES})
    assert run(ctx, FakeEmbedder()) == {"stories": 2}
    silver = ctx.storage.read_json(layers.silver_stories(RUN_DATE))
    assert silver["distance_threshold"] == 0.4
    assert len(silver["stories"]) == 2


def test_run_with_no_articles(ctx):
    ctx.storage.write_json(layers.bronze_articles(RUN_DATE), {"run_date": RUN_DATE, "articles": []})
    assert run(ctx, FakeEmbedder()) == {"stories": 0}
