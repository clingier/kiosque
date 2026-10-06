from datetime import datetime, timezone

from kiosque_pipeline.snapshot import build_snapshot, validate
from conftest import RUN_DATE, SOURCES

NOW = datetime(2026, 10, 6, 6, 31, 12, tzinfo=timezone.utc)

METRICS = {
    "run_date": RUN_DATE,
    "kpis": {"articles": 2, "media": 2, "stories": 1, "blind_spots": 0, "median_hhi": 5000.0,
             "group_article_share": {"bollore": 50.0, "niel": 50.0}},
    "collection": {"total_sources": 2, "success_count": 2, "failed": []},
    "stories": [{
        "id": f"{RUN_DATE}-001", "title": "Retraites : le vote reporté", "article_count": 2, "media_count": 2,
        "hhi": 5000.0, "dominant_group": "bollore", "dominant_share": 50.0, "blind_spot": None,
        "groups": {"bollore": 1, "niel": 1},
        "articles": [
            {"media": "cnews", "title": "a", "url": "https://cnews.fr/a", "date": None, "owner_group": "bollore", "influence": None},
            {"media": "le-monde", "title": "b", "url": "https://lemonde.fr/b", "date": None, "owner_group": "niel", "influence": None},
        ],
    }],
}


def test_build_snapshot_is_valid(groups):
    snap = build_snapshot(METRICS, SOURCES, groups, NOW)
    validate(snap)
    assert snap["generated_at"] == "2026-10-06T06:31:12Z"
    assert snap["date"] == RUN_DATE
    assert set(snap["stories"][0]["articles"][0]) == {"media", "title", "url", "date"}
    va = next(m for m in snap["media"] if m["slug"] == "valeurs-actuelles")
    assert va == {"slug": "valeurs-actuelles", "name": "Valeurs actuelles", "owner_group": "independant",
                  "influence": "sterin-pericles"}
