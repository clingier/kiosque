"""
ownership.py — silver/stories → silver/enriched.

Resolves each story's article ids to full articles tagged with the media's
owner_group (capital ownership, from sources.yaml) and optional influence
network (qualitative signal only, never used in metrics).
"""

from kiosque_pipeline import layers
from kiosque_pipeline.context import JobContext


def enrich(stories: list[dict], articles: list[dict], sources_by_slug: dict[str, dict]) -> list[dict]:
    by_id = {a["id"]: a for a in articles}
    enriched = []
    for story in stories:
        story_articles = []
        for article_id in story["article_ids"]:
            article = by_id[article_id]
            source = sources_by_slug[article["media"]]
            story_articles.append({
                "media": article["media"],
                "title": article["title"],
                "url": article["url"],
                "date": article["date"],
                "owner_group": source["owner_group"],
                "influence": source.get("influence"),
            })
        story_articles.sort(key=lambda x: (x["date"] or "", x["media"]))
        enriched.append({"id": story["id"], "title": story["title"], "articles": story_articles})
    return enriched


def run(ctx: JobContext) -> dict:
    articles = ctx.storage.read_json(layers.bronze_articles(ctx.run_date))["articles"]
    stories = ctx.storage.read_json(layers.silver_stories(ctx.run_date))["stories"]
    enriched = enrich(stories, articles, ctx.sources_by_slug)
    ctx.storage.write_json(layers.silver_enriched(ctx.run_date), {"run_date": ctx.run_date, "stories": enriched})
    return {"stories": len(enriched)}
