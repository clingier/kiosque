"""
cluster.py — bronze → silver/stories.

Groups headlines about the same event with agglomerative clustering on
sentence embeddings. A cluster becomes a story only if ≥ MIN_STORY_MEDIA
distinct media cover it.
"""

import logging
from collections import defaultdict

import numpy as np
from sklearn.cluster import AgglomerativeClustering

from kiosque_pipeline import layers
from kiosque_pipeline.context import JobContext
from kiosque_pipeline.embed import Embedder

logger = logging.getLogger(__name__)

DEFAULT_DISTANCE_THRESHOLD = 0.40  # cosine distance; calibrated in Task 10
MIN_STORY_MEDIA = 2


def cluster_labels(embeddings: np.ndarray, distance_threshold: float) -> list[int]:
    n = len(embeddings)
    if n < 2:
        return [0] * n
    model = AgglomerativeClustering(
        n_clusters=None, metric="cosine", linkage="average", distance_threshold=distance_threshold
    )
    return model.fit_predict(embeddings).tolist()


def build_stories(
    run_date: str,
    articles: list[dict],
    labels: list[int],
    embeddings: np.ndarray,
    min_media: int = MIN_STORY_MEDIA,
) -> list[dict]:
    members: dict[int, list[int]] = defaultdict(list)
    for index, label in enumerate(labels):
        members[label].append(index)

    candidates = []
    for indexes in members.values():
        media = {articles[i]["media"] for i in indexes}
        if len(media) < min_media:
            continue
        centroid = embeddings[indexes].mean(axis=0)
        representative = max(indexes, key=lambda i: (float(embeddings[i] @ centroid), -i))
        candidates.append({
            "title": articles[representative]["title"],
            "article_ids": sorted(articles[i]["id"] for i in indexes),
            "_media_count": len(media),
        })

    candidates.sort(key=lambda s: (-s["_media_count"], -len(s["article_ids"]), s["title"]))
    return [
        {"id": f"{run_date}-{rank:03d}", "title": c["title"], "article_ids": c["article_ids"]}
        for rank, c in enumerate(candidates, start=1)
    ]


def run(ctx: JobContext, embedder: Embedder, distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD) -> dict:
    articles = ctx.storage.read_json(layers.bronze_articles(ctx.run_date))["articles"]
    if articles:
        embeddings = embedder.encode([a["title"] for a in articles])
        stories = build_stories(ctx.run_date, articles, cluster_labels(embeddings, distance_threshold), embeddings)
    else:
        stories = []

    ctx.storage.write_json(layers.silver_stories(ctx.run_date), {
        "run_date": ctx.run_date,
        "distance_threshold": distance_threshold,
        "stories": stories,
    })
    logger.info("Clustered %d articles into %d stories", len(articles), len(stories))
    return {"stories": len(stories)}
