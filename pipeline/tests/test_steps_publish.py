import json
from datetime import datetime, timezone

import jsonschema
import pytest

from fakes import FakeEmbedder
from kiosque_pipeline import layers
from kiosque_pipeline.snapshot import validate
from kiosque_pipeline.steps import cluster, metrics, normalize, ownership, publish, ref
from spark_seed import write_raw, write_report
from conftest import RUN_DATE

pytestmark = pytest.mark.spark
NOW = datetime(2026, 10, 6, 6, 31, 0, tzinfo=timezone.utc)
TITLES = {
    "cnews": "Retraites : le vote reporté à l'Assemblée",
    "le-monde": "Retraites : pourquoi le vote est reporté",
    "franceinfo": "Le vote sur les retraites repoussé à demain",
    "mediapart": "Climat : un octobre record en France",
}


def build_day(ctx, titles=TITLES):
    ref.run(ctx)
    write_report(ctx, ok=tuple(titles))
    for i, (media, title) in enumerate(titles.items()):
        write_raw(ctx, media, [{"title": title, "url": f"https://{media}.fr/{i}", "date": "2026-10-05T20:00:00Z"}])
    normalize.run(ctx)
    cluster.run(ctx, FakeEmbedder, 0.4)
    ownership.run(ctx)
    metrics.run(ctx)


def snapshot_row(ctx):
    return ctx.spark.table("spark_catalog.gold.snapshots").collect()


def test_publish_writes_valid_snapshot_identical_to_table(sctx):
    build_day(sctx)
    result = publish.run(sctx, now=NOW)
    [row] = snapshot_row(sctx)
    doc = json.loads(row.snapshot_json)
    validate(doc)
    assert doc["date"] == RUN_DATE and doc["generated_at"] == "2026-10-06T06:31:00Z"
    assert doc["stories"][0]["groups"] == {"bollore": 1, "niel": 1, "public": 1}
    assert result["published"] == ["spark_catalog.gold.snapshots", layers.web_archive(RUN_DATE), layers.WEB_LATEST]
    web = sctx.storage.root / layers.WEB_LATEST
    assert web.read_bytes() == row.snapshot_json.encode("utf-8")


def test_publish_empty_day(sctx):
    ref.run(sctx)
    write_report(sctx, failed=("cnews",), ok=())
    normalize.run(sctx)
    cluster.run(sctx, FakeEmbedder, 0.4)
    ownership.run(sctx)
    metrics.run(sctx)
    assert publish.run(sctx, now=NOW)["stories"] == 0
    doc = json.loads(snapshot_row(sctx)[0].snapshot_json)
    validate(doc)
    assert doc["stories"] == [] and doc["kpis"]["median_hhi"] is None and doc["kpis"]["group_article_share"] == {}


def test_invalid_snapshot_is_never_written(sctx):
    build_day(sctx)
    sctx.spark.sql("UPDATE spark_catalog.gold.story_metrics SET blind_spot = 'editorial'")
    with pytest.raises(jsonschema.ValidationError):
        publish.run(sctx, now=NOW)
    assert not sctx.spark.catalog.tableExists("spark_catalog.gold.snapshots")
    assert not (sctx.storage.root / layers.WEB_LATEST).exists()


def test_backfill_does_not_replace_newer_live_snapshot(sctx):
    build_day(sctx)
    sctx.storage.write_json(layers.WEB_LATEST, {"date": "2026-10-07"})
    result = publish.run(sctx, now=NOW)
    assert sctx.storage.read_json(layers.WEB_LATEST) == {"date": "2026-10-07"}
    assert layers.WEB_LATEST not in result["published"]
    assert json.loads((sctx.storage.root / layers.web_archive(RUN_DATE)).read_text())["date"] == RUN_DATE


def test_rerun_is_idempotent(sctx):
    build_day(sctx)
    publish.run(sctx, now=NOW)
    first = snapshot_row(sctx)[0].snapshot_json
    publish.run(sctx, now=NOW)
    rows = snapshot_row(sctx)
    assert len(rows) == 1 and rows[0].snapshot_json == first


def test_groups_and_media_keep_config_order(sctx):
    # The frontend relies on config order (majors first in groups.yaml), as build_snapshot did.
    build_day(sctx)
    publish.run(sctx, now=NOW)
    doc = json.loads(snapshot_row(sctx)[0].snapshot_json)
    assert [g["id"] for g in doc["groups"]] == [g["id"] for g in sctx.groups]
    assert [m["slug"] for m in doc["media"]] == [s["slug"] for s in sctx.sources]
    assert set(doc["media"][0]) == {"slug", "name", "owner_group", "influence"}
