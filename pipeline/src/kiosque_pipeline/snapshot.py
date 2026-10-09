"""snapshot.py — The snapshot.json contract shared with the frontend."""

import json
from datetime import datetime
from functools import cache
from importlib.resources import files

import jsonschema

SCHEMA_VERSION = 1


@cache
def _schema() -> dict:
    return json.loads(files("kiosque_pipeline").joinpath("snapshot.schema.json").read_text(encoding="utf-8"))


def validate(doc: dict) -> None:
    """Raise jsonschema.ValidationError if doc does not match snapshot.schema.json."""
    jsonschema.validate(doc, _schema())


ARTICLE_FIELDS = ("media", "title", "url", "date")


def build_snapshot(metrics_doc: dict, sources: list[dict], groups: list[dict], generated_at: datetime) -> dict:
    stories = [
        {**story, "articles": [{k: a[k] for k in ARTICLE_FIELDS} for a in story["articles"]]}
        for story in metrics_doc["stories"]
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "date": metrics_doc["run_date"],
        "generated_at": generated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kpis": metrics_doc["kpis"],
        "collection": metrics_doc["collection"],
        "groups": [{"id": g["id"], "label": g["label"], "major": g["major"]} for g in groups],
        "media": [
            {"slug": s["slug"], "name": s["name"], "owner_group": s["owner_group"], "influence": s.get("influence")}
            for s in sources
        ],
        "stories": stories,
    }
