"""Smoke tests that don't require the heavy SpeechBrain model."""

from app.core.similarity import cosine_similarity, rank_reciters


def test_cosine_similarity_identical():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0


def test_rank_reciters_orders_by_score():
    import numpy as np

    db = {"a": np.array([1.0, 0.0]), "b": np.array([0.0, 1.0])}
    ranked = rank_reciters(np.array([1.0, 0.0]), db, top_k=2)
    assert ranked[0]["reciter"] == "a"
    assert ranked[0]["score"] > ranked[1]["score"]


def test_health_endpoint():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "reciters_loaded" in body
