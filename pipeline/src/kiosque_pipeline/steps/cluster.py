"""
steps/cluster.py — bronze.articles → silver.stories.

Agglomerative clustering needs every headline at once, and a day is a few thousand
rows, so the day is collected and embedded on the driver. A Python UDF would run the
model in a Spark Python worker, which serverless compute caps at far less memory
than torch plus the model need: the worker is killed and the stage aborts.
"""

import logging

import pandas as pd

from kiosque_pipeline.cluster import DEFAULT_DISTANCE_THRESHOLD, build_stories, cluster_labels
from kiosque_pipeline.context import JobContext
from kiosque_pipeline.embed import SentenceTransformerEmbedder
from kiosque_pipeline.tables import read_day, write_day

STORIES_SCHEMA = "run_date date, story_id string, title string, article_id string"

logger = logging.getLogger(__name__)


def _stories_for_day(embedder_factory, distance_threshold):
    def fn(pdf: pd.DataFrame) -> pd.DataFrame:
        if pdf.empty:
            return pd.DataFrame(columns=["run_date", "story_id", "title", "article_id"])
        pdf = pdf.sort_values(["media", "url"])
        articles = pdf[["id", "media", "title"]].to_dict("records")
        run_date = pdf["run_date"].iloc[0]
        embeddings = embedder_factory().encode([x["title"] for x in articles])
        labels = cluster_labels(embeddings, distance_threshold)
        stories = build_stories(str(run_date), articles, labels, embeddings)
        rows = [(run_date, s["id"], s["title"], aid) for s in stories for aid in s["article_ids"]]
        return pd.DataFrame(rows, columns=["run_date", "story_id", "title", "article_id"])

    return fn


def run(
    ctx: JobContext,
    embedder_factory=SentenceTransformerEmbedder,
    distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
) -> dict:
    articles = read_day(ctx, "bronze", "articles").select("run_date", "id", "media", "title", "url")
    logger.info(
        "Clustering %d articles for %s (distance threshold %.2f)", articles.count(), ctx.run_date, distance_threshold
    )
    stories_pdf = _stories_for_day(embedder_factory, distance_threshold)(articles.toPandas())
    logger.info("Embedded and clustered on the driver into %d story rows", len(stories_pdf))
    stories = ctx.spark.createDataFrame(stories_pdf, STORIES_SCHEMA)
    write_day(stories, ctx, "silver", "stories")
    stored = read_day(ctx, "silver", "stories")
    count = stored.select("story_id").distinct().count()
    logger.info("silver.stories holds %d stories covering %d articles", count, stored.count())
    return {"stories": count}
