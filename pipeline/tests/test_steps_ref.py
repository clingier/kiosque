import dataclasses

import pytest

from kiosque_pipeline.steps import ref

pytestmark = pytest.mark.spark


def test_ref_writes_sources_and_groups(sctx):
    assert ref.run(sctx) == {"sources": 10, "groups": 8}
    rows = {r.slug: r for r in sctx.spark.table("spark_catalog.ref.sources").collect()}
    assert rows["valeurs-actuelles"].influence == "sterin-pericles"
    assert rows["cnews"].influence is None
    assert rows["cnews"].owner_group == "bollore"
    assert sctx.spark.table("spark_catalog.ref.groups").where("major").count() == 6


def test_ref_rerun_overwrites(sctx):
    ref.run(sctx)
    ref.run(sctx)
    assert sctx.spark.table("spark_catalog.ref.sources").count() == 10


def test_ref_rejects_unknown_owner_group_before_writing(sctx):
    bad = dataclasses.replace(sctx, sources=[{"slug": "x", "name": "X", "owner_group": "nile"}])
    with pytest.raises(ValueError, match="nile"):
        ref.run(bad)
    assert not sctx.spark.catalog.tableExists("spark_catalog.ref.sources")
