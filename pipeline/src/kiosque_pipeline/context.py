"""context.py — Everything a pipeline step needs for one run."""

from dataclasses import dataclass
from functools import cached_property


@dataclass
class JobContext:
    storage: object  # LocalStorage | BlobStorage — only used to write $web
    run_date: str  # YYYY-MM-DD, UTC collection date
    sources: list[dict]
    groups: list[dict]
    spark: object = None  # pyspark.sql.SparkSession
    catalog: str = "kiosque"
    raw_root: str = "/Volumes/kiosque/raw/feeds"

    @cached_property
    def sources_by_slug(self) -> dict[str, dict]:
        return {s["slug"]: s for s in self.sources}

    @cached_property
    def major_groups(self) -> set[str]:
        return {g["id"] for g in self.groups if g["major"]}
