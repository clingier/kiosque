"""
metrics.py — silver/enriched → gold/metrics.

Concentration is measured on capital ownership only, over distinct media:
  - HHI: each independent media is its own owner; public service is one owner.
  - groups / dominant_group: aggregated owner_group breakdown.
  - blind_spot: see blind_spot().
The optional `influence` field is never used here.
"""

from collections import Counter
from statistics import median

from kiosque_pipeline import layers
from kiosque_pipeline.context import JobContext

INDEPENDANT = "independant"
MIN_MEDIA_IGNORED_BY_MAJORS = 3


def hhi(owner_media_counts: dict[str, int]) -> float:
    total = sum(owner_media_counts.values())
    if total == 0:
        return 0.0
    return round(sum((100 * n / total) ** 2 for n in owner_media_counts.values()), 1)


def owner_key(owner_group: str, media: str) -> str:
    return f"{INDEPENDANT}:{media}" if owner_group == INDEPENDANT else owner_group


def blind_spot(group_media: dict[str, int], media_count: int, major_groups: set[str]) -> str | None:
    if len(group_media) == 1 and INDEPENDANT not in group_media:
        return "single_group"
    if not major_groups & group_media.keys() and media_count >= MIN_MEDIA_IGNORED_BY_MAJORS:
        return "ignored_by_majors"
    return None


def story_metrics(story: dict, major_groups: set[str]) -> dict:
    media_owner = {a["media"]: a["owner_group"] for a in story["articles"]}
    groups = dict(sorted(Counter(media_owner.values()).items()))
    owners = Counter(owner_key(group, media) for media, group in media_owner.items())
    media_count = len(media_owner)
    dominant_group = min(groups, key=lambda g: (-groups[g], g))
    return {
        **story,
        "article_count": len(story["articles"]),
        "media_count": media_count,
        "hhi": hhi(owners),
        "dominant_group": dominant_group,
        "dominant_share": round(100 * groups[dominant_group] / media_count, 1),
        "blind_spot": blind_spot(groups, media_count, major_groups),
        "groups": groups,
    }


def day_kpis(stories: list[dict], articles: list[dict], sources_by_slug: dict[str, dict]) -> dict:
    by_group = Counter(sources_by_slug[a["media"]]["owner_group"] for a in articles)
    total = len(articles)
    return {
        "articles": total,
        "media": len({a["media"] for a in articles}),
        "stories": len(stories),
        "blind_spots": sum(1 for s in stories if s["blind_spot"]),
        "median_hhi": median(s["hhi"] for s in stories) if stories else None,
        "group_article_share": {g: round(100 * n / total, 1) for g, n in sorted(by_group.items())},
    }


def run(ctx: JobContext) -> dict:
    bronze = ctx.storage.read_json(layers.bronze_articles(ctx.run_date))
    enriched = ctx.storage.read_json(layers.silver_enriched(ctx.run_date))["stories"]
    stories = [story_metrics(s, ctx.major_groups) for s in enriched]
    kpis = day_kpis(stories, bronze["articles"], ctx.sources_by_slug)
    ctx.storage.write_json(layers.gold_metrics(ctx.run_date), {
        "run_date": ctx.run_date,
        "kpis": kpis,
        "collection": bronze["collection"],
        "stories": stories,
    })
    return {"stories": len(stories), "blind_spots": kpis["blind_spots"]}
