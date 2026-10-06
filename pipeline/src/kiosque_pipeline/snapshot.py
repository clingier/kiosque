"""snapshot.py — The snapshot.json contract shared with the frontend."""

import json
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
