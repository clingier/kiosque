"""spark_seed.py — Build raw files and read tables back for Spark step tests."""

import json
from pathlib import Path

TS = "yyyy-MM-dd'T'HH:mm:ss'Z'"


def _day_dir(ctx) -> Path:
    path = Path(ctx.raw_root) / ctx.run_date
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_raw(ctx, media: str, articles: list[dict], method: str = "rss") -> None:
    doc = {"media": media, "collected_at": "2026-10-06T06:04:00Z", "source_method": method,
           "feed_url": "", "article_count": len(articles), "articles": articles}
    (_day_dir(ctx) / f"{media}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def write_report(ctx, finished_at: str = "2026-10-06T06:04:00Z", failed=(), ok=("cnews",)) -> None:
    sources = [{"slug": s, "status": "error"} for s in failed] + [{"slug": s, "status": "ok"} for s in ok]
    doc = {"finished_at": finished_at, "total_sources": len(sources), "success_count": len(ok), "sources": sources}
    (_day_dir(ctx) / "_report.json").write_text(json.dumps(doc, indent=2), encoding="utf-8")


def bronze_rows(ctx) -> list[tuple]:
    from pyspark.sql import functions as F

    df = ctx.spark.table(f"{ctx.catalog}.bronze.articles").where(F.col("run_date") == F.to_date(F.lit(ctx.run_date)))
    return sorted(
        (r.media, r.url, r.title, r.id, r.date, r.source_method)
        for r in df.select("media", "url", "title", "id", F.date_format("date", TS).alias("date"), "source_method").collect()
    )


BRONZE_SCHEMA = "run_date date, id string, media string, title string, url string, date timestamp, source_method string"


def seed_bronze(ctx, articles: list[dict]) -> None:
    from pyspark.sql import functions as F

    from kiosque_pipeline.tables import write_day

    rows = [(a["id"], a["media"], a["title"], a["url"], a.get("date"), a.get("source_method", "rss")) for a in articles]
    df = ctx.spark.createDataFrame(rows, "id string, media string, title string, url string, date string, source_method string")
    df = df.select(
        F.to_date(F.lit(ctx.run_date)).alias("run_date"), "id", "media", "title", "url",
        F.try_to_timestamp("date", F.lit(TS)).alias("date"), "source_method",
    )
    write_day(df, ctx, "bronze", "articles")
