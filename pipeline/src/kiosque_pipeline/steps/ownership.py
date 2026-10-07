"""
steps/ownership.py — silver.stories + bronze.articles + ref.sources → silver.story_articles.

A plain join, so UC column lineage links owner_group back to ref.sources.
"""

import logging

from pyspark.sql import functions as F

from kiosque_pipeline.context import JobContext
from kiosque_pipeline.tables import read_day, table, write_day

logger = logging.getLogger(__name__)


def run(ctx: JobContext) -> dict:
    stories = read_day(ctx, "silver", "stories").select("run_date", "story_id", "article_id")
    articles = read_day(ctx, "bronze", "articles").select(
        F.col("id").alias("article_id"), "media", "title", "url", "date"
    )
    sources = ctx.spark.table(table(ctx, "ref", "sources")).select(
        F.col("slug").alias("media"), "owner_group", "influence"
    )
    story_articles = stories.join(articles, "article_id").join(sources, "media").select(
        "run_date", "story_id", "article_id", "media", "title", "url", "date", "owner_group", "influence"
    )
    write_day(story_articles, ctx, "silver", "story_articles")
    stored = read_day(ctx, "silver", "story_articles")
    count = stored.select("story_id").distinct().count()
    logger.info("silver.story_articles holds %d articles across %d stories", stored.count(), count)
    return {"stories": count}
