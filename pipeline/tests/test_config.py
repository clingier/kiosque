import pytest

from kiosque_pipeline.config import load_sources, validate_config
from conftest import REPO_ROOT


def test_real_config_is_valid(groups):
    sources = load_sources(REPO_ROOT / "config" / "sources.yaml")
    validate_config(sources, groups)
    assert len(sources) >= 60


def test_unknown_owner_group_rejected(groups):
    sources = [{"slug": "le-monde", "name": "Le Monde", "owner_group": "nile"}]
    with pytest.raises(ValueError, match="le-monde.*nile"):
        validate_config(sources, groups)


def test_duplicate_slug_rejected(groups):
    sources = [
        {"slug": "le-monde", "name": "Le Monde", "owner_group": "niel"},
        {"slug": "le-monde", "name": "Le Monde bis", "owner_group": "niel"},
    ]
    with pytest.raises(ValueError, match="duplicate slug.*le-monde"):
        validate_config(sources, groups)


def test_exactly_six_major_groups(groups):
    assert sum(1 for g in groups if g["major"]) == 6
