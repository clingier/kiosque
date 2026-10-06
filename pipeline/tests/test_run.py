from datetime import datetime, timezone

from kiosque_pipeline import layers
from kiosque_pipeline.run import run_all
from conftest import RUN_DATE
from test_cluster import FakeEmbedder

NOW = datetime(2026, 10, 6, 6, 31, 0, tzinfo=timezone.utc)


def seed_raw(storage):
    storage.write_json(layers.raw_report(RUN_DATE), {
        "finished_at": "2026-10-06T06:04:00Z", "total_sources": 4, "success_count": 4,
        "sources": [{"slug": s, "status": "ok"} for s in ("cnews", "le-monde", "franceinfo", "mediapart")],
    })
    titles = {
        "cnews": "Retraites : le vote reporté à l'Assemblée",
        "le-monde": "Retraites : pourquoi le vote est reporté",
        "franceinfo": "Le vote sur les retraites repoussé à demain",
        "mediapart": "Climat : un octobre record en France",
    }
    for i, (media, title) in enumerate(titles.items()):
        storage.write_json(f"{layers.raw_dir(RUN_DATE)}/{media}.json", {
            "media": media, "collected_at": "2026-10-06T06:04:00Z", "source_method": "rss", "feed_url": "",
            "article_count": 1, "articles": [{"title": title, "url": f"https://{media}.fr/{i}", "date": "2026-10-05T20:00:00Z"}],
        })


def test_run_all_end_to_end(ctx):
    seed_raw(ctx.storage)
    result = run_all(ctx, FakeEmbedder(), now=NOW)
    assert result["normalize"] == {"articles": 4}
    assert result["cluster"] == {"stories": 1}
    snap = ctx.storage.read_json(layers.WEB_LATEST)
    assert snap["stories"][0]["groups"] == {"bollore": 1, "niel": 1, "public": 1}


def test_run_all_is_idempotent(ctx):
    seed_raw(ctx.storage)
    run_all(ctx, FakeEmbedder(), now=NOW)
    first = ctx.storage.read_json(layers.WEB_LATEST)
    run_all(ctx, FakeEmbedder(), now=NOW)
    assert ctx.storage.read_json(layers.WEB_LATEST) == first


def test_run_all_passes_threshold(ctx):
    seed_raw(ctx.storage)
    run_all(ctx, FakeEmbedder(), now=NOW, distance_threshold=0.1)
    assert ctx.storage.read_json(layers.silver_stories(RUN_DATE))["distance_threshold"] == 0.1
