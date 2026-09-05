"""Cosine-similarity matching utilities (numpy only)."""

from __future__ import annotations

import numpy as np


def l2_normalize(vec: np.ndarray) -> np.ndarray:
    vec = np.asarray(vec, dtype=np.float64).flatten()
    norm = np.linalg.norm(vec)
    if norm == 0:
        return vec
    return vec / norm


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float64).flatten()
    b = np.asarray(b, dtype=np.float64).flatten()
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def rank_reciters(
    query_emb: np.ndarray,
    database: dict[str, np.ndarray],
    top_k: int = 3,
) -> list[dict[str, float]]:
    """Return top-k ``{"reciter": name, "score": cosine}`` sorted by score desc."""
    query = l2_normalize(query_emb)
    scored: list[dict] = []
    from scripts.sources import RECITERS  # noqa: PLC0415 - display names for API

    for name, ref in database.items():
        ref_n = l2_normalize(np.asarray(ref))
        if ref_n.size == 0 or query.size == 0:
            continue
        if ref_n.shape != query.shape:
            # Skip incompatible vectors instead of crashing the request.
            continue
        spec = RECITERS.get(name)
        scored.append({
            "reciter": name,
            "display": spec.display if spec else name,
            "score": cosine_similarity(query, ref_n),
        })
    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[: max(top_k, 1)]
