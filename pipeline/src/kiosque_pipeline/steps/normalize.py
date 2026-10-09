"""
steps/normalize.py — raw volume → bronze.articles, bronze.collections.

Same rules as the reference kiosque_pipeline.normalize (D5, D6): canonical URL
dedupe keeping the earliest date, ≥ 4-word titles, http(s) only, known media,
24h window ending at the collection's finished_at (+1h), null dates kept.
"""

import json
import logging
import os
from datetime import datetime

from pyspark.sql import Window
from pyspark.sql import functions as F
from pyspark.sql import types as T

from kiosque_pipeline import normalize as reference
from kiosque_pipeline.context import JobContext
from kiosque_pipeline.tables import table, write_day

TS = "yyyy-MM-dd'T'HH:mm:ss'Z'"
RAW_SCHEMA = (
    "media string, collected_at string, source_method string, feed_url string, article_count long, "
    "articles array<struct<title: string, url: string, date: string>>"
)

logger = logging.getLogger(__name__)

canonical_url = F.udf(reference.canonical_url, T.StringType())
clean_title = F.udf(reference.clean_title, T.StringType())


def _parse_ts(column):
    return F.try_to_timestamp(column, F.lit(TS))


def run(ctx: JobContext) -> dict:
    spark = ctx.spark
    day_dir = f"{ctx.raw_root}/{ctx.run_date}"
    report_path = f"{day_dir}/_report.json"
    logger.info("Reading collector report %s", report_path)
    if not os.path.exists(report_path):
        raise reference.RawDataMissing(f"{report_path} not found — did the collector run on {ctx.run_date}?")
    run_date = F.to_date(F.lit(ctx.run_date))

    # Spark skips files whose name starts with "_" (hidden metadata), even when named
    # explicitly, so the collector's _report.json is read in Python. bronze.collections
    # therefore has no lineage edge from the volume; bronze.articles keeps it.
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    reference_time = datetime.fromisoformat(report["finished_at"].replace("Z", "+00:00"))
    failed = sorted(s["slug"] for s in report["sources"] if s["status"] == "error")
    logger.info(
        "Collection finished at %s: %d/%d sources succeeded",
        report["finished_at"], report["success_count"], report["total_sources"],
    )
    if failed:
        logger.warning("%d sources failed collection: %s", len(failed), ", ".join(failed))
    collections = spark.createDataFrame(
        [(
            reference_time,
            report["total_sources"],
            report["success_count"],
            failed,
        )],
        "reference_time timestamp, total_sources long, success_count long, failed array<string>",
    ).select(run_date.alias("run_date"), "reference_time", "total_sources", "success_count", "failed")
    write_day(collections, ctx, "bronze", "collections")

    lower, upper = reference_time - reference.WINDOW_BEFORE, reference_time + reference.WINDOW_AFTER
    logger.info("Keeping articles dated between %s and %s (or undated)", lower.isoformat(), upper.isoformat())

    media_files = sorted(
        f"{day_dir}/{name}" for name in os.listdir(day_dir) if name.endswith(".json") and name != "_report.json"
    )
    logger.info("Found %d media files in %s", len(media_files), day_dir)
    if not media_files:
        logger.warning("No media files for %s; bronze.articles will be empty", ctx.run_date)
    raw = (
        spark.read.schema(RAW_SCHEMA).option("multiLine", True).json(media_files)
        if media_files
        else spark.createDataFrame([], RAW_SCHEMA)
    )
    known = spark.table(table(ctx, "ref", "sources")).select(F.col("slug").alias("media"))

    candidates = (
        raw.select("media", "source_method", F.posexplode("articles").alias("pos", "a"))
        .join(known, "media", "left_semi")
        .select(
            "media",
            "source_method",
            "pos",
            clean_title(F.coalesce(F.col("a.title"), F.lit(""))).alias("title"),
            canonical_url(F.col("a.url")).alias("url"),
            _parse_ts(F.col("a.date")).alias("date"),
        )
        .where(F.size(F.split(F.trim("title"), r"\s+")) >= reference.MIN_TITLE_WORDS)
        .where(F.col("url").rlike("^https?://"))
        .where(F.col("date").isNull() | F.col("date").between(F.lit(lower), F.lit(upper)))
    )
    earliest_first = Window.partitionBy("url").orderBy(F.col("date").asc_nulls_last(), "media", "pos")
    articles = (
        candidates.withColumn("rank", F.row_number().over(earliest_first))
        .where(F.col("rank") == 1)
        .select(
            run_date.alias("run_date"),
            F.substring(F.sha1(F.col("url")), 1, 16).alias("id"),
            "media",
            "title",
            "url",
            "date",
            "source_method",
        )
    )
    write_day(articles, ctx, "bronze", "articles")
    count = spark.table(table(ctx, "bronze", "articles")).where(F.col("run_date") == run_date).count()
    logger.info("bronze.articles holds %d deduplicated articles for %s", count, ctx.run_date)
    return {"articles": count}
