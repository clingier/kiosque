"""
steps/metrics.py — silver.story_articles → gold.story_metrics, gold.day_kpis.

D10–D12 in Spark SQL: concentration over distinct media; each independent media
is its own owner for HHI; dominant group by distinct media (ties → group id asc);
blind spots against ref.groups.major. bround() matches Python's round().
"""

import logging

from pyspark.sql import Window
from pyspark.sql import functions as F

from kiosque_pipeline.context import JobContext
from kiosque_pipeline.metrics import INDEPENDANT, MIN_MEDIA_IGNORED_BY_MAJORS
from kiosque_pipeline.tables import read_day, table, write_day

logger = logging.getLogger(__name__)


def _story_metrics(ctx: JobContext):
    spark = ctx.spark
    story_articles = read_day(ctx, "silver", "story_articles")
    titles = read_day(ctx, "silver", "stories").select("story_id", "title").distinct()
    majors = spark.table(table(ctx, "ref", "groups")).select(F.col("id").alias("owner_group"), "major")

    media_owner = story_articles.select("run_date", "story_id", "media", "owner_group").distinct()
    per_story = story_articles.groupBy("run_date", "story_id").agg(
        F.count("*").alias("article_count"), F.countDistinct("media").alias("media_count")
    )
    per_group = media_owner.groupBy("story_id", "owner_group").agg(F.count("*").cast("int").alias("n"))
    dominant = (
        per_group.withColumn(
            "rank", F.row_number().over(Window.partitionBy("story_id").orderBy(F.col("n").desc(), "owner_group"))
        )
        .where("rank = 1")
        .select("story_id", F.col("owner_group").alias("dominant_group"), F.col("n").alias("dominant_n"))
    )
    groups = (
        per_group.join(majors, "owner_group")
        .groupBy("story_id")
        .agg(
            F.map_from_entries(F.array_sort(F.collect_list(F.struct("owner_group", "n")))).alias("groups"),
            F.count("*").alias("n_groups"),
            F.max(F.col("major").cast("int")).alias("has_major"),
        )
    )
    owner_key = F.when(F.col("owner_group") == INDEPENDANT, F.concat(F.lit(f"{INDEPENDANT}:"), "media")).otherwise(
        F.col("owner_group")
    )
    hhi = (
        media_owner.withColumn("owner_key", owner_key)
        .groupBy("story_id", "owner_key")
        .agg(F.count("*").alias("n"))
        .join(per_story.select("story_id", "media_count"), "story_id")
        .groupBy("story_id")
        .agg(F.bround(F.sum(F.pow(F.lit(100.0) * F.col("n") / F.col("media_count"), 2)), 1).alias("hhi"))
    )
    blind_spot = (
        F.when((F.col("n_groups") == 1) & (F.col("dominant_group") != INDEPENDANT), F.lit("single_group"))
        .when((F.col("has_major") == 0) & (F.col("media_count") >= MIN_MEDIA_IGNORED_BY_MAJORS), F.lit("ignored_by_majors"))
    )
    return (
        per_story.join(titles, "story_id")
        .join(hhi, "story_id")
        .join(dominant, "story_id")
        .join(groups, "story_id")
        .select(
            "run_date",
            "story_id",
            "title",
            "article_count",
            "media_count",
            "hhi",
            "dominant_group",
            F.bround(F.lit(100.0) * F.col("dominant_n") / F.col("media_count"), 1).alias("dominant_share"),
            blind_spot.alias("blind_spot"),
            "groups",
        )
    )


def _day_kpis(ctx: JobContext):
    spark = ctx.spark
    articles = read_day(ctx, "bronze", "articles")
    sources = spark.table(table(ctx, "ref", "sources")).select(F.col("slug").alias("media"), "owner_group")
    story_metrics = read_day(ctx, "gold", "story_metrics")

    counts = articles.agg(F.count("*").alias("articles"), F.countDistinct("media").alias("media"))
    stories = story_metrics.agg(
        F.count("*").alias("stories"),
        F.count("blind_spot").alias("blind_spots"),
        F.expr("percentile(hhi, 0.5)").alias("median_hhi"),
    )
    share = (
        articles.join(sources, "media")
        .groupBy("owner_group")
        .agg(F.count("*").alias("n"))
        .withColumn("share", F.bround(F.lit(100.0) * F.col("n") / F.sum("n").over(Window.partitionBy()), 1))
        .agg(F.map_from_entries(F.array_sort(F.collect_list(F.struct("owner_group", "share")))).alias("group_article_share"))
    )
    return counts.crossJoin(stories).crossJoin(share).select(
        F.to_date(F.lit(ctx.run_date)).alias("run_date"),
        "articles",
        "media",
        "stories",
        "blind_spots",
        "median_hhi",
        "group_article_share",
    )


def run(ctx: JobContext) -> dict:
    write_day(_story_metrics(ctx), ctx, "gold", "story_metrics")
    write_day(_day_kpis(ctx), ctx, "gold", "day_kpis")
    row = read_day(ctx, "gold", "day_kpis").first()
    logger.info(
        "Day KPIs for %s: %d articles from %d media, %d stories, %d blind spots, median HHI %s",
        ctx.run_date, row["articles"], row["media"], row["stories"], row["blind_spots"], row["median_hhi"],
    )
    return {"stories": row["stories"], "blind_spots": row["blind_spots"]}
