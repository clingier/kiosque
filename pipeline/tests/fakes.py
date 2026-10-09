"""fakes.py — Test doubles importable by Spark Python workers (PYTHONPATH set in conftest)."""

import numpy as np

TOPICS = {"retraites": [1.0, 0.0, 0.0], "climat": [0.0, 1.0, 0.0]}


class FakeEmbedder:
    """Maps a headline to its topic axis; unknown topics get a unique axis each."""

    def encode(self, texts):
        rows = []
        for i, text in enumerate(texts):
            vec = next((v for k, v in TOPICS.items() if k in text.lower()), None)
            if vec is None:
                vec = [0.0, 0.0, 0.0] + [1.0 if j == i else 0.0 for j in range(len(texts))]
            else:
                vec = vec + [0.0] * len(texts)
            rows.append(vec)
        width = max(len(r) for r in rows)
        arr = np.array([r + [0.0] * (width - len(r)) for r in rows])
        return arr / np.linalg.norm(arr, axis=1, keepdims=True)
