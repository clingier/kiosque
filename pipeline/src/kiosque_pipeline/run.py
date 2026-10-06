"""run.py — Run every Spark step for one day, in order (local runs and tests)."""

from datetime import datetime

from kiosque_pipeline.cluster import DEFAULT_DISTANCE_THRESHOLD
from kiosque_pipeline.context import JobContext
from kiosque_pipeline.steps import cluster, metrics, normalize, ownership, publish, ref


def run_all(
    ctx: JobContext,
    embedder_factory,
    now: datetime | None = None,
    distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
) -> dict:
    return {
        "ref": ref.run(ctx),
        "normalize": normalize.run(ctx),
        "cluster": cluster.run(ctx, embedder_factory, distance_threshold),
        "ownership": ownership.run(ctx),
        "metrics": metrics.run(ctx),
        "publish": publish.run(ctx, now=now),
    }
