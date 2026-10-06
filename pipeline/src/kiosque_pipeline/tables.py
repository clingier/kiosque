"""
tables.py — Unity Catalog table naming and day-scoped Delta writes.

Every non-ref table is partitioned by run_date; write_day replaces exactly one
day so re-runs are idempotent.
"""

from pyspark.sql import Column, DataFrame
from pyspark.sql import functions as F

from kiosque_pipeline.context import JobContext


def table(ctx: JobContext, schema: str, name: str) -> str:
    return f"{ctx.catalog}.{schema}.{name}"


def day(ctx: JobContext) -> Column:
    return F.col("run_date") == F.to_date(F.lit(ctx.run_date))


def read_day(ctx: JobContext, schema: str, name: str) -> DataFrame:
    return ctx.spark.table(table(ctx, schema, name)).where(day(ctx))


def write_day(df: DataFrame, ctx: JobContext, schema: str, name: str) -> None:
    target = table(ctx, schema, name)
    if not ctx.spark.catalog.tableExists(target):
        df.writeTo(target).using("delta").partitionedBy(F.col("run_date")).create()
    else:
        # Replaces exactly this day's rows (DataFrameWriterV2 overwrite-by-condition).
        df.writeTo(target).overwrite(day(ctx))


def write_full(df: DataFrame, ctx: JobContext, schema: str, name: str) -> None:
    df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(table(ctx, schema, name))
