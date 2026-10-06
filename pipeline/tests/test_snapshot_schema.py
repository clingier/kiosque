import copy

import jsonschema
import pytest

from kiosque_pipeline.snapshot import validate

VALID = {
    "schema_version": 1,
    "date": "2026-10-06",
    "generated_at": "2026-10-06T06:31:12Z",
    "kpis": {"articles": 4, "media": 3, "stories": 1, "blind_spots": 0, "median_hhi": 3333.3,
             "group_article_share": {"bollore": 50.0, "niel": 25.0, "public": 25.0}},
    "collection": {"total_sources": 3, "success_count": 3, "failed": []},
    "groups": [{"id": "bollore", "label": "Bolloré / Vivendi", "major": True}],
    "media": [{"slug": "cnews", "name": "CNews", "owner_group": "bollore", "influence": None}],
    "stories": [{
        "id": "2026-10-06-001", "title": "Réforme des retraites : le vote reporté",
        "article_count": 2, "media_count": 2, "hhi": 5000.0,
        "dominant_group": "bollore", "dominant_share": 50.0, "blind_spot": None,
        "groups": {"bollore": 1, "niel": 1},
        "articles": [
            {"media": "cnews", "title": "Retraites : vote reporté", "url": "https://www.cnews.fr/a", "date": "2026-10-05T20:00:00Z"},
            {"media": "le-monde", "title": "Le vote sur les retraites reporté", "url": "https://www.lemonde.fr/b", "date": None},
        ],
    }],
}


def test_valid_snapshot_passes():
    validate(VALID)


def test_empty_day_is_valid():
    doc = copy.deepcopy(VALID)
    doc["stories"] = []
    doc["kpis"]["median_hhi"] = None
    validate(doc)


@pytest.mark.parametrize("mutate", [
    lambda d: d.pop("stories"),
    lambda d: d.__setitem__("schema_version", 2),
    lambda d: d["stories"][0].__setitem__("blind_spot", "editorial_bias"),
    lambda d: d["stories"][0]["articles"][0].__setitem__("summary", "republished text"),
    lambda d: d["stories"][0]["articles"][0].__setitem__("url", "javascript:alert(1)"),
])
def test_invalid_snapshots_rejected(mutate):
    doc = copy.deepcopy(VALID)
    mutate(doc)
    with pytest.raises(jsonschema.ValidationError):
        validate(doc)
