import os
import sys
import tempfile
import types
from pathlib import Path

from kiosque_pipeline.embed import MODEL_NAME, SentenceTransformerEmbedder


def _fake_model(monkeypatch, calls):
    class FakeModel:
        def __init__(self, name, device=None):
            calls["args"] = (name, device)

    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=FakeModel))


def test_device_is_passed_to_the_model(monkeypatch):
    calls = {}
    _fake_model(monkeypatch, calls)
    SentenceTransformerEmbedder(device="cpu")
    assert calls["args"] == (MODEL_NAME, "cpu")


def test_hf_home_untouched_when_home_is_writable(monkeypatch, tmp_path):
    _fake_model(monkeypatch, {})
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    SentenceTransformerEmbedder()
    assert "HF_HOME" not in os.environ


def test_hf_home_moved_to_temp_when_home_is_read_only(monkeypatch, tmp_path):
    # Databricks serverless workers run with a home directory that cannot be created; every
    # Hugging Face cache (hub and xet) lives under HF_HOME, so it must point somewhere writable.
    _fake_model(monkeypatch, {})
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "missing")
    SentenceTransformerEmbedder()
    assert os.environ["HF_HOME"] == str(Path(tempfile.gettempdir()) / "hf-home")


def test_existing_hf_home_is_kept(monkeypatch, tmp_path):
    _fake_model(monkeypatch, {})
    monkeypatch.setenv("HF_HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "missing")
    SentenceTransformerEmbedder()
    assert os.environ["HF_HOME"] == str(tmp_path)
