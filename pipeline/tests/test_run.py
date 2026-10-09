from datetime import datetime, timezone

import pytest

from fakes import FakeEmbedder
from kiosque_pipeline import layers
from kiosque_pipeline.run import run_all
from spark_seed import write_raw, write_report

pytestmark = pytest.mark.spark
NOW = datetime(2026, 10, 6, 6, 31, 0, tzinfo=timezone.utc)
TITLES = {
    "cnews": "Retraites : le vote reporté à l'Assemblée",
    "le-monde": "Retraites : pourquoi le vote est reporté",
    "franceinfo": "Le vote sur les retraites repoussé à demain",
    "mediapart": "Climat : un octobre record en France",
}


def seed_raw(ctx):
    write_report(ctx, ok=tuple(TITLES))
    for i, (media, title) in enumerate(TITLES.items()):
        write_raw(ctx, media, [{"title": title, "url": f"https://{media}.fr/{i}", "date": "2026-10-05T20:00:00Z"}])


def test_run_all_end_to_end(sctx):
    seed_raw(sctx)
    result = run_all(sctx, FakeEmbedder, now=NOW, distance_threshold=0.4)
    assert list(result) == ["ref", "normalize", "cluster", "ownership", "metrics", "publish"]
    assert result["normalize"] == {"articles": 4}
    assert result["cluster"] == {"stories": 1}
    assert sctx.storage.read_json(layers.WEB_LATEST)["stories"][0]["groups"] == {"bollore": 1, "niel": 1, "public": 1}


def test_run_all_is_idempotent(sctx):
    seed_raw(sctx)
    run_all(sctx, FakeEmbedder, now=NOW, distance_threshold=0.4)
    first = (sctx.storage.root / layers.WEB_LATEST).read_bytes()
    run_all(sctx, FakeEmbedder, now=NOW, distance_threshold=0.4)
    assert (sctx.storage.root / layers.WEB_LATEST).read_bytes() == first
