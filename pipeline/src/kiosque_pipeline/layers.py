"""layers.py — Where the published snapshot lives on the static website ($web)."""

WEB_LATEST = "$web/snapshot.json"


def web_archive(run_date: str) -> str:
    return f"$web/snapshots/{run_date}.json"
