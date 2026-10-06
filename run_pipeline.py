"""
run_pipeline.py — Run the Kiosque processing pipeline locally.

Reads ./output/raw/feeds/YYYY-MM-DD/ (written by run_local.py) and writes
Delta tables in a temporary local warehouse, then $web/snapshot.json under ./output.
Usage: python run_pipeline.py [--date YYYY-MM-DD] [--output ./output] [--threshold 0.40]
Requires: pip install -e "pipeline[spark,embed]" and Java 21.
"""

import argparse
import functools
import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from kiosque_pipeline.cluster import DEFAULT_DISTANCE_THRESHOLD
from kiosque_pipeline.config import load_groups, load_sources, validate_config
from kiosque_pipeline.context import JobContext
from kiosque_pipeline.embed import SentenceTransformerEmbedder
from kiosque_pipeline.job import resolve_run_date
from kiosque_pipeline.local_spark import ensure_schemas, local_session
from kiosque_pipeline.run import run_all
from kiosque_pipeline.storage import LocalStorage

CONFIG_DIR = Path(__file__).parent / "config"


def main():
    parser = argparse.ArgumentParser(description="Run the Kiosque pipeline locally (Spark + Delta)")
    parser.add_argument("--date", default="", help="Run date YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--output", default="./output", help="Root holding raw/feeds and receiving $web")
    parser.add_argument("--threshold", type=float, default=DEFAULT_DISTANCE_THRESHOLD,
                        help="Clustering cosine distance threshold")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                        datefmt="%H:%M:%S")

    sources = load_sources(CONFIG_DIR / "sources.yaml")
    groups = load_groups(CONFIG_DIR / "groups.yaml")
    validate_config(sources, groups)

    with tempfile.TemporaryDirectory(prefix="kiosque-warehouse-") as warehouse:
        spark = local_session(warehouse)
        ensure_schemas(spark)
        ctx = JobContext(
            storage=LocalStorage(args.output),
            run_date=resolve_run_date(args.date, datetime.now(timezone.utc)),
            sources=sources,
            groups=groups,
            spark=spark,
            catalog="spark_catalog",
            raw_root=str(Path(args.output) / "raw" / "feeds"),
        )
        # CPU: Spark forks Python workers, and PyTorch's macOS Metal backend breaks after fork.
        embedder_factory = functools.partial(SentenceTransformerEmbedder, device="cpu")
        result = run_all(ctx, embedder_factory, distance_threshold=args.threshold)
        spark.stop()

    print(json.dumps(result, indent=2))
    print(f"\n📁 Snapshot: {args.output}/$web/snapshot.json")


if __name__ == "__main__":
    main()
