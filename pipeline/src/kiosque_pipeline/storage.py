"""
storage.py — Read/write JSON documents in the medallion containers.

Two backends share one interface: LocalStorage (tests, run_pipeline.py) and
BlobStorage (Databricks, via the ADLS connection string). Paths are
"<container>/<blob path>", e.g. "bronze/articles/2026-10-06.json".
"""

import json
from pathlib import Path
from typing import Any

CONTENT_TYPE_JSON = "application/json; charset=utf-8"


def _dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


class LocalStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def read_json(self, path: str) -> Any:
        with open(self.root / path, "r", encoding="utf-8") as f:
            return json.load(f)

    def write_json(self, path: str, data: Any, cache_control: str | None = None) -> None:
        full_path = self.root / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(_dumps(data), encoding="utf-8")

    def exists(self, path: str) -> bool:
        return (self.root / path).is_file()

    def list(self, prefix: str) -> list[str]:
        base = self.root / prefix
        if not base.is_dir():
            return []
        return sorted(str(p.relative_to(self.root)) for p in base.iterdir() if p.is_file())


class BlobStorage:
    def __init__(self, connection_string: str):
        from azure.storage.blob import BlobServiceClient

        self._service = BlobServiceClient.from_connection_string(connection_string)

    def _split(self, path: str):
        container, _, blob = path.partition("/")
        return self._service.get_container_client(container), blob

    def read_json(self, path: str) -> Any:
        container_client, blob = self._split(path)
        return json.loads(container_client.download_blob(blob).readall())

    def write_json(self, path: str, data: Any, cache_control: str | None = None) -> None:
        from azure.storage.blob import ContentSettings

        container_client, blob = self._split(path)
        container_client.upload_blob(
            blob,
            _dumps(data).encode("utf-8"),
            overwrite=True,
            content_settings=ContentSettings(content_type=CONTENT_TYPE_JSON, cache_control=cache_control),
        )

    def exists(self, path: str) -> bool:
        container_client, blob = self._split(path)
        return container_client.get_blob_client(blob).exists()

    def list(self, prefix: str) -> list[str]:
        container_client, blob_prefix = self._split(prefix)
        container = prefix.partition("/")[0]
        start = blob_prefix.rstrip("/") + "/"
        names = [
            b.name
            for b in container_client.list_blobs(name_starts_with=start)
            if "/" not in b.name[len(start):]
        ]
        return sorted(f"{container}/{name}" for name in names)
