import dataclasses
from datetime import date

import pytest

from kiosque_pipeline.tables import read_day, table, write_day, write_full

pytestmark = pytest.mark.spark


def test_table_uses_context_catalog(sctx):
    assert table(sctx, "bronze", "articles") == "spark_catalog.bronze.articles"


def test_write_day_creates_then_replaces_only_that_day(sctx):
    spark = sctx.spark
    write_day(spark.createDataFrame([(date(2026, 10, 6), "a")], "run_date date, v string"), sctx, "bronze", "t")
    other = dataclasses.replace(sctx, run_date="2026-10-05")
    write_day(spark.createDataFrame([(date(2026, 10, 5), "x")], "run_date date, v string"), other, "bronze", "t")
    write_day(spark.createDataFrame([(date(2026, 10, 6), "b")], "run_date date, v string"), sctx, "bronze", "t")

    rows = sorted((r.run_date.isoformat(), r.v) for r in spark.table("spark_catalog.bronze.t").collect())
    assert rows == [("2026-10-05", "x"), ("2026-10-06", "b")]
    assert [r.v for r in read_day(sctx, "bronze", "t").collect()] == ["b"]


def test_write_full_replaces_everything(sctx):
    spark = sctx.spark
    write_full(spark.createDataFrame([("a",)], "v string"), sctx, "ref", "t")
    write_full(spark.createDataFrame([("b",), ("c",)], "v string"), sctx, "ref", "t")
    assert sorted(r.v for r in spark.table("spark_catalog.ref.t").collect()) == ["b", "c"]


def test_session_time_zone_is_utc(spark):
    assert spark.conf.get("spark.sql.session.timeZone") == "UTC"
