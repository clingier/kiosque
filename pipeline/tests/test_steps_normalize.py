from datetime import datetime, timezone
from pathlib import Path

import pytest

from kiosque_pipeline.normalize import RawDataMissing, normalize_articles
from kiosque_pipeline.steps import normalize, ref
from spark_seed import bronze_rows, write_raw, write_report

pytestmark = pytest.mark.spark
REF_TIME = datetime(2026, 10, 6, 6, 4, 0, tzinfo=timezone.utc)


def art(title, url, date="2026-10-05T18:00:00Z"):
    return {"title": title, "url": url, "date": date}


MIXED = {
    "le-monde": [
        art("Le gouvernement présente son budget 2027", "https://www.lemonde.fr/a.html?utm_source=x", "2026-10-05T20:00:00Z"),
        art("Le gouvernement présente son budget 2027", "https://www.lemonde.fr/a.html#top", "2026-10-05T19:00:00Z"),
        art("Retraites&nbsp;:  l&#39;Assemblée   vote le texte", "HTTPS://WWW.LeMonde.fr/b/"),
    ],
    "cnews": [
        art("Article bien dans la fenêtre du jour", "https://cnews.fr/1", "2026-10-05T06:04:00Z"),
        art("Article trop ancien pour la journée", "https://cnews.fr/2", "2026-10-05T05:00:00Z"),
        art("Article daté dans un futur lointain", "https://cnews.fr/3", "2026-10-06T09:00:00Z"),
        art("Article sans aucune date de publication", "https://cnews.fr/4", None),
        art("Direct", "https://cnews.fr/live"),
        art("Un titre parfaitement valable ici", "javascript:void(0)"),
    ],
    "unknown-media": [art("Un titre parfaitement valable ici", "https://x.fr/1")],
}


def seed_mixed(ctx):
    ref.run(ctx)
    write_report(ctx)
    for media, articles in MIXED.items():
        write_raw(ctx, media, articles, method="gnews" if media == "cnews" else "rss")


def reference_rows(ctx):
    files = [{"media": m, "source_method": "gnews" if m == "cnews" else "rss", "articles": a} for m, a in sorted(MIXED.items())]
    return sorted(
        (a["media"], a["url"], a["title"], a["id"], a["date"], a["source_method"])
        for a in normalize_articles(files, REF_TIME, set(ctx.sources_by_slug))
    )


def test_matches_reference_implementation(sctx):
    seed_mixed(sctx)
    result = normalize.run(sctx)
    assert bronze_rows(sctx) == reference_rows(sctx)
    assert result == {"articles": len(reference_rows(sctx))}


def test_dates_keep_utc_instant(sctx):
    seed_mixed(sctx)
    normalize.run(sctx)
    dates = {r[1]: r[4] for r in bronze_rows(sctx)}
    assert dates["https://cnews.fr/1"] == "2026-10-05T06:04:00Z"  # exact lower window bound kept
    assert dates["https://cnews.fr/4"] is None


def test_missing_report_raises(sctx):
    ref.run(sctx)
    write_raw(sctx, "cnews", [art("Un titre parfaitement valable ici", "https://cnews.fr/1")])
    with pytest.raises(RawDataMissing):
        normalize.run(sctx)


def test_empty_day_writes_collection_and_no_articles(sctx):
    ref.run(sctx)
    write_report(sctx, failed=("le-monde", "tf1-info"), ok=("cnews",))
    assert normalize.run(sctx) == {"articles": 0}
    [row] = sctx.spark.table("spark_catalog.bronze.collections").collect()
    assert (row.total_sources, row.success_count, list(row.failed)) == (3, 1, ["le-monde", "tf1-info"])


def test_corrupt_raw_file_is_skipped(sctx):
    seed_mixed(sctx)
    (Path(sctx.raw_root) / sctx.run_date / "blast.json").write_text('{"media": "blast", "articles": [', encoding="utf-8")
    normalize.run(sctx)
    assert bronze_rows(sctx) == reference_rows(sctx)


def test_dedupe_is_deterministic(sctx):
    ref.run(sctx)
    write_report(sctx)
    write_raw(sctx, "cnews", [
        art("Premier titre pour la même adresse", "https://cnews.fr/same", "2026-10-05T10:00:00Z"),
        art("Second titre pour la même adresse", "https://cnews.fr/same", "2026-10-05T10:00:00Z"),
    ])
    normalize.run(sctx)
    first = bronze_rows(sctx)
    normalize.run(sctx)
    assert bronze_rows(sctx) == first
    assert [r[2] for r in first] == ["Premier titre pour la même adresse"]
