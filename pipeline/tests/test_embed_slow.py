import numpy as np
import pytest


@pytest.mark.slow
def test_real_model_puts_paraphrases_closer_than_unrelated():
    from kiosque_pipeline.embed import SentenceTransformerEmbedder

    emb = SentenceTransformerEmbedder().encode([
        "Retraites : le vote reporté à l'Assemblée nationale",
        "L'Assemblée repousse le vote sur la réforme des retraites",
        "Ligue des champions : le PSG s'impose à Munich",
    ])
    assert np.allclose(np.linalg.norm(emb, axis=1), 1.0, atol=1e-5)
    assert emb[0] @ emb[1] > emb[0] @ emb[2] + 0.2
