# backend/app/core/similarity.py
import numpy as np

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = a.flatten()
    b = b.flatten()
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)

def find_best_match(query_emb, reciters_db, top_k=3):
    scores = {}
    for name, ref_emb in reciters_db.items():
        scores[name] = cosine_similarity(query_emb, ref_emb)
    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top = sorted_items[:top_k]
    result = {
        "reciter": top[0][0],
        "confidence": float(top[0][1]),
        "top_3": [{"name": n, "score": float(s)} for n, s in top]
    }
    return result
