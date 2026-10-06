"""context.py — Everything a pipeline step needs for one run."""

from dataclasses import dataclass
from functools import cached_property


@dataclass
class JobContext:
    storage: object  # LocalStorage | BlobStorage
    run_date: str  # YYYY-MM-DD, UTC collection date
    sources: list[dict]
    groups: list[dict]

    @cached_property
    def sources_by_slug(self) -> dict[str, dict]:
        return {s["slug"]: s for s in self.sources}

    @cached_property
    def major_groups(self) -> set[str]:
        return {g["id"] for g in self.groups if g["major"]}
