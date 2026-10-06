"""
publish.py — gold/metrics → gold/snapshots + $web.

The snapshot is validated against the schema before anything is written, and
$web/snapshot.json (what the site reads) is written last.
"""

from datetime import datetime, timezone

from kiosque_pipeline import layers
from kiosque_pipeline.context import JobContext
from kiosque_pipeline.snapshot import build_snapshot, validate

CACHE_LATEST = "public, max-age=300"
CACHE_ARCHIVE = "public, max-age=86400"


def _live_snapshot_is_newer(ctx: JobContext) -> bool:
    """A backfill of a past day must not replace the site's current snapshot."""
    if not ctx.storage.exists(layers.WEB_LATEST):
        return False
    return ctx.storage.read_json(layers.WEB_LATEST).get("date", "") > ctx.run_date


def run(ctx: JobContext, now: datetime | None = None) -> dict:
    metrics_doc = ctx.storage.read_json(layers.gold_metrics(ctx.run_date))
    snapshot = build_snapshot(metrics_doc, ctx.sources, ctx.groups, now or datetime.now(timezone.utc))
    validate(snapshot)

    targets = [
        (layers.gold_snapshot(ctx.run_date), None),
        (layers.web_archive(ctx.run_date), CACHE_ARCHIVE),
    ]
    if not _live_snapshot_is_newer(ctx):
        targets.append((layers.WEB_LATEST, CACHE_LATEST))
    for path, cache_control in targets:
        ctx.storage.write_json(path, snapshot, cache_control=cache_control)
    return {"stories": len(snapshot["stories"]), "published": [path for path, _ in targets]}
