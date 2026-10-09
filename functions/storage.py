"""
storage.py — Abstraction layer for writing JSON files to ADLS Gen2 or local filesystem.

Provides a factory function that returns the appropriate writer based on configuration.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def _write_to_local(base_dir: str, container_name: str, blob_path: str, data: dict) -> None:
    """Write a JSON file to the local filesystem (for development/testing)."""
    full_path = Path(base_dir) / container_name / blob_path
    full_path.parent.mkdir(parents=True, exist_ok=True)

    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.debug("Wrote local file: %s", full_path)


def _write_to_adls(
    container_name: str,
    blob_path: str,
    data: dict,
    connection_string: str,
) -> None:
    """Write a JSON file to Azure Data Lake Storage Gen2."""
    from azure.storage.blob import BlobServiceClient, ContentSettings

    blob_service = BlobServiceClient.from_connection_string(connection_string)
    blob_client = blob_service.get_blob_client(
        container=container_name, blob=blob_path
    )

    content = json.dumps(data, ensure_ascii=False, indent=2)
    blob_client.upload_blob(
        content,
        overwrite=True,
        content_settings=ContentSettings(
            content_type="application/json; charset=utf-8"
        ),
    )

    logger.debug("Wrote blob: %s/%s", container_name, blob_path)


class StorageWriter:
    """
    Unified storage writer that dispatches to local filesystem or ADLS Gen2.

    Usage:
        writer = StorageWriter.from_env()
        writer.write("feeds/2026-07-03/le-monde.json", data_dict)
    """

    def __init__(
        self,
        mode: str,
        container_name: str = "raw",
        connection_string: str | None = None,
        local_dir: str | None = None,
    ):
        self.mode = mode  # "adls" or "local"
        self.container_name = container_name
        self.connection_string = connection_string
        self.local_dir = local_dir

    @classmethod
    def from_env(cls) -> "StorageWriter":
        """
        Create a StorageWriter from environment variables.

        If DATALAKE_STORAGE_CONNECTION_STRING is set and non-empty, uses ADLS.
        Otherwise falls back to LOCAL_OUTPUT_DIR (defaults to ./output).
        """
        connection_string = os.environ.get(
            "DATALAKE_STORAGE_CONNECTION_STRING", ""
        )
        container = os.environ.get("CONTAINER_RAW", "raw")

        if connection_string:
            logger.info("Storage mode: ADLS Gen2 (container=%s)", container)
            return cls(
                mode="adls",
                container_name=container,
                connection_string=connection_string,
            )
        else:
            local_dir = os.environ.get("LOCAL_OUTPUT_DIR", "./output")
            logger.info("Storage mode: local filesystem (%s)", local_dir)
            return cls(
                mode="local",
                container_name=container,
                local_dir=local_dir,
            )

    def write(self, blob_path: str, data: dict) -> None:
        """Write a JSON dict to the configured storage backend."""
        if self.mode == "adls":
            _write_to_adls(
                self.container_name,
                blob_path,
                data,
                self.connection_string,
            )
        else:
            _write_to_local(self.local_dir, self.container_name, blob_path, data)

    def read_json(self, container: str, blob_path: str) -> dict | None:
        """Read a JSON document from any container. Returns None if it does not exist."""
        if self.mode == "adls":
            from azure.core.exceptions import ResourceNotFoundError
            from azure.storage.blob import BlobServiceClient

            blob_service = BlobServiceClient.from_connection_string(self.connection_string)
            blob_client = blob_service.get_blob_client(container=container, blob=blob_path)
            try:
                return json.loads(blob_client.download_blob().readall())
            except ResourceNotFoundError:
                return None

        full_path = Path(self.local_dir) / container / blob_path
        if not full_path.exists():
            return None
        with open(full_path, "r", encoding="utf-8") as f:
            return json.load(f)
