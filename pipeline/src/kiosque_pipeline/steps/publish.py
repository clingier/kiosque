"""
steps/publish.py — gold tables → gold.snapshots → $web.

One Spark plan assembles the snapshot JSON from the upstream tables. The driver
validates it against snapshot.schema.json before anything is written; the same
plan is then written to gold.snapshots (keeping lineage) and the validated
string is uploaded byte-for-byte to $web. A backfill never replaces a newer
live snapshot.
"""

import json
from datetime import datetime, timezone

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from kiosque_pipeline import layers
from kiosque_pipeline.context import JobContext
from kiosque_pipeline.snapshot import SCHEMA_VERSION, validate
from kiosque_pipeline.tables import read_day, table, write_day

TS = "yyyy-MM-dd'T'HH:mm:ss'Z'"
CACHE_LATEST = "public, max-age=300"
CACHE_ARCHIVE = "public, max-age=86400"
JSON_OPTIONS = {"ignoreNullFields": "false"}


def _by(field: str):
    return lambda left, right: F.when(left[field] < right[field], -1).when(left[field] > right[field], 1).otherwise(0)


def snapshot_frame(ctx: JobContext, generated_at: str) -> DataFrame:
    spark = ctx.spark
    kpis = read_day(ctx, "gold", "day_kpis").select(
        F.struct("articles", "media", "stories", "blind_spots", "median_hhi", "group_article_share").alias("kpis")
    )
    collection = read_day(ctx, "bronze", "collections").select(
        F.struct("total_sources", "success_count", "failed").alias("collection")
    )
    groups = spark.table(table(ctx, "ref", "groups")).agg(
        F.array_sort(F.collect_list(F.struct("id", "label", "major")), _by("id")).alias("groups")
    )
    media = spark.table(table(ctx, "ref", "sources")).agg(
        F.array_sort(F.collect_list(F.struct("slug", "name", "owner_group", "influence")), _by("slug")).alias("media")
    )
    date_str = F.date_format("date", TS)
    articles = (
        read_day(ctx, "silver", "story_articles")
        .groupBy("story_id")
        .agg(F.sort_array(F.collect_list(F.struct(
            F.coalesce(date_str, F.lit("")).alias("sort_key"), "media", "title", "url", date_str.alias("date")
        ))).alias("sorted"))
        .select("story_id", F.transform("sorted", lambda a: F.struct(
            a["media"].alias("media"), a["title"].alias("title"), a["url"].alias("url"), a["date"].alias("date")
        )).alias("articles"))
    )
    stories = read_day(ctx, "gold", "story_metrics").join(articles, "story_id").agg(
        F.array_sort(F.collect_list(F.struct(
            F.col("story_id").alias("id"), "title", "article_count", "media_count", "hhi",
            "dominant_group", "dominant_share", "blind_spot", "groups", "articles",
        )), _by("id")).alias("stories")
    )
    document = F.struct(
        F.lit(SCHEMA_VERSION).alias("schema_version"),
        F.lit(ctx.run_date).alias("date"),
        F.lit(generated_at).alias("generated_at"),
        "kpis", "collection", "groups", "media",
        F.coalesce("stories", F.array()).alias("stories"),
    )
    return kpis.crossJoin(collection).crossJoin(groups).crossJoin(media).crossJoin(stories).select(
        F.to_date(F.lit(ctx.run_date)).alias("run_date"),
        F.lit(generated_at).alias("generated_at"),
        F.lit(SCHEMA_VERSION).alias("schema_version"),
        F.to_json(document, JSON_OPTIONS).alias("snapshot_json"),
    )


def _live_snapshot_is_newer(ctx: JobContext) -> bool:
    if not ctx.storage.exists(layers.WEB_LATEST):
        return False
    return ctx.storage.read_json(layers.WEB_LATEST).get("date", "") > ctx.run_date


def run(ctx: JobContext, now: datetime | None = None) -> dict:
    generated_at = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    frame = snapshot_frame(ctx, generated_at)
    row = frame.first()
    if row is None:
        raise RuntimeError(f"no gold data to publish for {ctx.run_date}")
    document = json.loads(row["snapshot_json"])
    validate(document)

    write_day(frame, ctx, "gold", "snapshots")
    published = [table(ctx, "gold", "snapshots")]
    ctx.storage.write_text(layers.web_archive(ctx.run_date), row["snapshot_json"], cache_control=CACHE_ARCHIVE)
    published.append(layers.web_archive(ctx.run_date))
    if not _live_snapshot_is_newer(ctx):
        ctx.storage.write_text(layers.WEB_LATEST, row["snapshot_json"], cache_control=CACHE_LATEST)
        published.append(layers.WEB_LATEST)
    return {"stories": len(document["stories"]), "published": published}
