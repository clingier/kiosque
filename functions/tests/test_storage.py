"""Tests for storage.py — local backend layout and reads."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from storage import StorageWriter


class TestLocalStorageWriter:
    def test_write_goes_under_container_dir(self, tmp_path):
        writer = StorageWriter(mode="local", container_name="raw", local_dir=str(tmp_path))
        writer.write("feeds/2026-10-06/le-monde.json", {"media": "le-monde"})

        written = tmp_path / "raw" / "feeds" / "2026-10-06" / "le-monde.json"
        assert json.loads(written.read_text(encoding="utf-8")) == {"media": "le-monde"}

    def test_write_keeps_non_ascii(self, tmp_path):
        writer = StorageWriter(mode="local", container_name="raw", local_dir=str(tmp_path))
        writer.write("x.json", {"title": "Réforme des retraites"})

        assert "Réforme" in (tmp_path / "raw" / "x.json").read_text(encoding="utf-8")

    def test_read_json_returns_document(self, tmp_path):
        (tmp_path / "$web").mkdir()
        (tmp_path / "$web" / "snapshot.json").write_text('{"date": "2026-10-06"}', encoding="utf-8")
        writer = StorageWriter(mode="local", local_dir=str(tmp_path))

        assert writer.read_json("$web", "snapshot.json") == {"date": "2026-10-06"}

    def test_read_json_missing_returns_none(self, tmp_path):
        writer = StorageWriter(mode="local", local_dir=str(tmp_path))

        assert writer.read_json("$web", "snapshot.json") is None
