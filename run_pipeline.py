"""
run_pipeline.py — Run the Kiosque processing pipeline locally.

Reads ./output/raw/feeds/YYYY-MM-DD/ (written by run_local.py) and writes
bronze/silver/gold and $web/snapshot.json under ./output.
Usage: python run_pipeline.py [--date YYYY-MM-DD] [--output ./output] [--threshold 0.40]
Requires: pip install -e "pipeline[embed]"
"""

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from kiosque_pipeline import cluster
from kiosque_pipeline.config import load_groups, load_sources, validate_config
from kiosque_pipeline.context import JobContext
from kiosque_pipeline.embed import SentenceTransformerEmbedder
from kiosque_pipeline.job import resolve_run_date
from kiosque_pipeline.run import run_all
from kiosque_pipeline.storage import LocalStorage

CONFIG_DIR = Path(__file__).parent / "config"


def main():
    parser = argparse.ArgumentParser(description="Run the Kiosque pipeline locally")
    parser.add_argument("--date", default="", help="Run date YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--output", default="./output", help="Local storage root (default: ./output)")
    parser.add_argument("--threshold", type=float, default=cluster.DEFAULT_DISTANCE_THRESHOLD,
                        help="Clustering cosine distance threshold")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                        datefmt="%H:%M:%S")

    sources = load_sources(CONFIG_DIR / "sources.yaml")
    groups = load_groups(CONFIG_DIR / "groups.yaml")
    validate_config(sources, groups)
    ctx = JobContext(LocalStorage(args.output), resolve_run_date(args.date, datetime.now(timezone.utc)), sources, groups)

    result = run_all(ctx, SentenceTransformerEmbedder(), distance_threshold=args.threshold)
    print(json.dumps(result, indent=2))
    print(f"\n📁 Snapshot: {args.output}/$web/snapshot.json")


if __name__ == "__main__":
    main()
