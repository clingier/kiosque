"""
cli.py — `kiosque-step`, the entry point every Databricks job task runs.

On serverless compute each task is a python_wheel_task calling this with the
job parameters, e.g. `kiosque-step --step normalize --run-date "" --catalog
kiosque --config-dir /Workspace/.../config`. Only publish reads the storage
secret (to upload $web/snapshot.json).
"""

import argparse
import json
from datetime import datetime, timezone

from kiosque_pipeline.config import load_groups, load_sources, validate_config
from kiosque_pipeline.context import JobContext
from kiosque_pipeline.embed import SentenceTransformerEmbedder
from kiosque_pipeline.job import SECRET_KEY, SECRET_SCOPE, resolve_run_date
from kiosque_pipeline.steps import cluster, metrics, normalize, ownership, publish, ref
from kiosque_pipeline.storage import BlobStorage

steps = {
    "ref": ref,
    "normalize": normalize,
    "cluster": cluster,
    "ownership": ownership,
    "metrics": metrics,
    "publish": publish,
}


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="kiosque-step", description="Run one Kiosque pipeline step")
    parser.add_argument("--step", required=True, choices=list(steps))
    parser.add_argument("--run-date", default="", help="YYYY-MM-DD; empty means today (UTC)")
    parser.add_argument("--catalog", required=True)
    parser.add_argument("--config-dir", required=True)
    return parser.parse_args(argv)


def build_context(args: argparse.Namespace, spark, get_secret) -> JobContext:
    sources = load_sources(f"{args.config_dir}/sources.yaml")
    groups = load_groups(f"{args.config_dir}/groups.yaml")
    validate_config(sources, groups)
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    web = args.step == "publish"
    return JobContext(
        storage=BlobStorage(get_secret(SECRET_SCOPE, SECRET_KEY)) if web else None,
        run_date=resolve_run_date(args.run_date, datetime.now(timezone.utc)),
        sources=sources,
        groups=groups,
        spark=spark,
        catalog=args.catalog,
        raw_root=f"/Volumes/{args.catalog}/raw/feeds",
    )


def _dbutils_secret(scope: str, key: str) -> str:
    from databricks.sdk.runtime import dbutils

    return dbutils.secrets.get(scope=scope, key=key)


def main(argv: list[str] | None = None, spark=None, get_secret=None) -> dict:
    args = parse_args(argv)
    if spark is None:
        from pyspark.sql import SparkSession

        spark = SparkSession.builder.getOrCreate()
    ctx = build_context(args, spark, get_secret or _dbutils_secret)
    if args.step == "cluster":
        result = steps["cluster"].run(ctx, SentenceTransformerEmbedder)
    else:
        result = steps[args.step].run(ctx)
    print(json.dumps({"step": args.step, "run_date": ctx.run_date, "result": result}))
    return result
