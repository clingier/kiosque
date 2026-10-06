"""config.py — Load and validate sources.yaml and groups.yaml."""

from pathlib import Path

import yaml


def _load_yaml_list(path: str | Path) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_sources(path: str | Path) -> list[dict]:
    return _load_yaml_list(path)


def load_groups(path: str | Path) -> list[dict]:
    return _load_yaml_list(path)


def validate_config(sources: list[dict], groups: list[dict]) -> None:
    """Raise ValueError on duplicate slugs or an owner_group missing from groups.yaml."""
    group_ids = {g["id"] for g in groups}
    seen: set[str] = set()
    for source in sources:
        slug = source["slug"]
        if slug in seen:
            raise ValueError(f"duplicate slug in sources.yaml: {slug}")
        seen.add(slug)
        if source["owner_group"] not in group_ids:
            raise ValueError(f"{slug}: unknown owner_group '{source['owner_group']}'")
