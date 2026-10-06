"""Shared fixtures for pipeline tests."""

from pathlib import Path

import pytest

from kiosque_pipeline.config import load_groups
from kiosque_pipeline.context import JobContext
from kiosque_pipeline.storage import LocalStorage

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_DATE = "2026-10-06"

SOURCES = [
    {"slug": "cnews", "name": "CNews", "owner_group": "bollore", "feeds": []},
    {"slug": "europe-1", "name": "Europe 1", "owner_group": "bollore", "feeds": []},
    {"slug": "le-monde", "name": "Le Monde", "owner_group": "niel", "feeds": []},
    {"slug": "tf1-info", "name": "TF1 Info", "owner_group": "bouygues", "feeds": []},
    {"slug": "franceinfo", "name": "France Info", "owner_group": "public", "feeds": []},
    {"slug": "france-inter", "name": "France Inter", "owner_group": "public", "feeds": []},
    {"slug": "mediapart", "name": "Mediapart", "owner_group": "independant", "feeds": []},
    {"slug": "reporterre", "name": "Reporterre", "owner_group": "independant", "feeds": []},
    {"slug": "blast", "name": "Blast", "owner_group": "independant", "feeds": []},
    {"slug": "valeurs-actuelles", "name": "Valeurs actuelles", "owner_group": "independant",
     "influence": "sterin-pericles", "feeds": []},
]


@pytest.fixture
def groups():
    return load_groups(REPO_ROOT / "config" / "groups.yaml")


@pytest.fixture
def ctx(tmp_path, groups):
    return JobContext(storage=LocalStorage(tmp_path), run_date=RUN_DATE, sources=SOURCES, groups=groups)
