"""
steps/ref.py — config/*.yaml → ref.sources, ref.groups.

The ownership reference data lives in the catalog so every downstream
owner_group is traceable to it (and its Delta history is the audit record of
ownership changes).
"""

import logging

from kiosque_pipeline.config import validate_config
from kiosque_pipeline.context import JobContext
from kiosque_pipeline.tables import write_full

# position keeps the YAML order, which the published snapshot preserves (majors first in groups.yaml).
SOURCES_SCHEMA = "position int, slug string, name string, owner_group string, influence string"
GROUPS_SCHEMA = "position int, id string, label string, major boolean"

logger = logging.getLogger(__name__)


def run(ctx: JobContext) -> dict:
    validate_config(ctx.sources, ctx.groups)
    sources = ctx.spark.createDataFrame(
        [(i, s["slug"], s["name"], s["owner_group"], s.get("influence")) for i, s in enumerate(ctx.sources)],
        SOURCES_SCHEMA,
    )
    groups = ctx.spark.createDataFrame(
        [(i, g["id"], g["label"], bool(g["major"])) for i, g in enumerate(ctx.groups)], GROUPS_SCHEMA
    )
    write_full(sources, ctx, "ref", "sources")
    write_full(groups, ctx, "ref", "groups")
    logger.info(
        "Wrote %d sources and %d groups (%d major)", len(ctx.sources), len(ctx.groups), len(ctx.major_groups)
    )
    return {"sources": len(ctx.sources), "groups": len(ctx.groups)}
