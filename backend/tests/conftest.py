"""Shared fixtures: fake embedding fn + fake profile DB (no heavy model)."""

from __future__ import annotations

import io

import numpy as np
import pytest
import soundfile as sf


@pytest.fixture
def wav_bytes() -> bytes:
    """A tiny valid 16 kHz mono wav (~0.5 s of silence)."""
    buf = io.BytesIO()
    sf.write(buf, np.zeros(8000, dtype="float32"), 16000, format="wav")
    return buf.getvalue()


@pytest.fixture
def fake_env(monkeypatch, tmp_path):
    """Point the service at a fake 2-reciter DB and stub the embedding fn.

    Returns (db, embed_stub) so tests can control query vectors.
    """
    from app.services import reciter_service

    db = {
        "alpha": np.array([1.0, 0.0, 0.0]),
        "beta": np.array([0.0, 1.0, 0.0]),
    }
    monkeypatch.setattr(reciter_service, "_db", db)

    queries = {"vector": np.array([1.0, 0.0, 0.0])}

    def fake_embed(waveform, sr=16000):
        return queries["vector"]

    import app.core.embeddings as emb

    monkeypatch.setattr(reciter_service, "embedding_from_waveform", fake_embed)
    monkeypatch.setattr(emb, "embedding_from_waveform", fake_embed)
    return db, queries
