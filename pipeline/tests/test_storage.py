from unittest.mock import MagicMock

from kiosque_pipeline.storage import BlobStorage, LocalStorage


class TestLocalStorage:
    def test_round_trip(self, tmp_path):
        storage = LocalStorage(tmp_path)
        storage.write_json("bronze/articles/2026-10-06.json", [{"title": "Été caniculaire"}])

        assert storage.read_json("bronze/articles/2026-10-06.json") == [{"title": "Été caniculaire"}]
        assert storage.exists("bronze/articles/2026-10-06.json")
        assert not storage.exists("bronze/articles/2026-10-05.json")

    def test_list_returns_direct_children_sorted(self, tmp_path):
        storage = LocalStorage(tmp_path)
        storage.write_json("raw/feeds/2026-10-06/le-monde.json", {})
        storage.write_json("raw/feeds/2026-10-06/cnews.json", {})
        storage.write_json("raw/feeds/2026-10-06/sub/deep.json", {})

        assert storage.list("raw/feeds/2026-10-06") == [
            "raw/feeds/2026-10-06/cnews.json",
            "raw/feeds/2026-10-06/le-monde.json",
        ]

    def test_list_missing_prefix_is_empty(self, tmp_path):
        assert LocalStorage(tmp_path).list("raw/feeds/1999-01-01") == []


class TestBlobStorage:
    def _storage_with(self, container_client):
        storage = BlobStorage.__new__(BlobStorage)
        storage._service = MagicMock()
        storage._service.get_container_client.return_value = container_client
        return storage

    def test_list_filters_to_direct_children(self):
        cc = MagicMock()
        blobs = []
        for name in ["feeds/2026-10-06/cnews.json", "feeds/2026-10-06/sub/deep.json", "feeds/2026-10-06/a.json"]:
            blob = MagicMock()
            blob.name = name
            blobs.append(blob)
        cc.list_blobs.return_value = blobs

        result = self._storage_with(cc).list("raw/feeds/2026-10-06")

        cc.list_blobs.assert_called_once_with(name_starts_with="feeds/2026-10-06/")
        assert result == ["raw/feeds/2026-10-06/a.json", "raw/feeds/2026-10-06/cnews.json"]

    def test_write_sets_content_type_and_cache_control(self):
        cc = MagicMock()
        self._storage_with(cc).write_json("$web/snapshot.json", {"a": 1}, cache_control="public, max-age=300")

        _, kwargs = cc.upload_blob.call_args
        assert kwargs["overwrite"] is True
        assert kwargs["content_settings"].content_type == "application/json; charset=utf-8"
        assert kwargs["content_settings"].cache_control == "public, max-age=300"
