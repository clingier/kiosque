import sys
import types

from kiosque_pipeline.embed import MODEL_NAME, SentenceTransformerEmbedder


def test_device_is_passed_to_the_model(monkeypatch):
    calls = {}

    class FakeModel:
        def __init__(self, name, device=None):
            calls["args"] = (name, device)

    monkeypatch.setitem(sys.modules, "sentence_transformers", types.SimpleNamespace(SentenceTransformer=FakeModel))
    SentenceTransformerEmbedder(device="cpu")
    assert calls["args"] == (MODEL_NAME, "cpu")
