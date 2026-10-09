"""
cli.py — `kiosque-step`, the entry point every Databricks job task runs.

On serverless compute each task is a python_wheel_task calling this with the
job parameters, e.g. `kiosque-step --step normalize --run-date "" --catalog
kiosque --config-dir /Workspace/.../config`. Only publish reads the storage
secret (to upload $web/snapshot.json).
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone

from kiosque_pipeline.config import load_groups, load_sources, validate_config
from kiosque_pipeline.context import JobContext
from kiosque_pipeline.embed import SentenceTransformerEmbedder
from kiosque_pipeline.job import SECRET_KEY, SECRET_SCOPE, resolve_run_date
from kiosque_pipeline.steps import cluster, metrics, normalize, ownership, publish, ref
from kiosque_pipeline.storage import BlobStorage

logger = logging.getLogger(__name__)

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

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


def configure_logging(level: int = logging.INFO) -> None:
    """Send the package's logs to stdout, which the Databricks task run page shows."""
    package = logging.getLogger("kiosque_pipeline")
    package.setLevel(level)
    if not any(getattr(h, "_kiosque", False) for h in package.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt="%Y-%m-%dT%H:%M:%SZ"))
        handler.formatter.converter = time.gmtime
        handler._kiosque = True
        package.addHandler(handler)
    # Our handler already prints; propagating would duplicate lines under the driver's root handler.
    package.propagate = False


def build_context(args: argparse.Namespace, spark, get_secret) -> JobContext:
    sources = load_sources(f"{args.config_dir}/sources.yaml")
    groups = load_groups(f"{args.config_dir}/groups.yaml")
    validate_config(sources, groups)
    logger.info("Loaded config from %s: %d sources, %d groups", args.config_dir, len(sources), len(groups))
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    web = args.step == "publish"
    if web:
        logger.info("Reading storage secret %s/%s", SECRET_SCOPE, SECRET_KEY)
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
    configure_logging()
    logger.info(
        "Starting step %s (run_date=%r, catalog=%s, config_dir=%s)",
        args.step, args.run_date, args.catalog, args.config_dir,
    )
    started = time.monotonic()
    if spark is None:
        from pyspark.sql import SparkSession

        spark = SparkSession.builder.getOrCreate()
        logger.info("Spark session ready (version %s)", spark.version)
    ctx = build_context(args, spark, get_secret or _dbutils_secret)
    logger.info("Resolved run date %s; raw root %s", ctx.run_date, ctx.raw_root)
    try:
        if args.step == "cluster":
            result = steps["cluster"].run(ctx, SentenceTransformerEmbedder)
        else:
            result = steps[args.step].run(ctx)
    except Exception:
        logger.exception("Step %s failed for %s after %.1fs", args.step, ctx.run_date, time.monotonic() - started)
        raise
    logger.info("Step %s finished for %s in %.1fs: %s", args.step, ctx.run_date, time.monotonic() - started, result)
    print(json.dumps({"step": args.step, "run_date": ctx.run_date, "result": result}))
    return result
