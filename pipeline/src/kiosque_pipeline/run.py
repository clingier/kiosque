"""run.py — Run every step for one day, in order (local runs and tests)."""

from datetime import datetime

from kiosque_pipeline import cluster, metrics, normalize, ownership, publish
from kiosque_pipeline.context import JobContext
from kiosque_pipeline.embed import Embedder


def run_all(
    ctx: JobContext,
    embedder: Embedder,
    now: datetime | None = None,
    distance_threshold: float = cluster.DEFAULT_DISTANCE_THRESHOLD,
) -> dict:
    return {
        "normalize": normalize.run(ctx),
        "cluster": cluster.run(ctx, embedder, distance_threshold),
        "ownership": ownership.run(ctx),
        "metrics": metrics.run(ctx),
        "publish": publish.run(ctx, now=now),
    }
