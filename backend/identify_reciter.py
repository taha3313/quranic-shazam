# identify_reciter.py
import numpy as np
from scipy.spatial.distance import cosine
from extract_embeddings import compute_embedding

# Load once, fast (milliseconds)
print("🔹 Loading reciters embeddings...")
reciters_embeddings = np.load("data/reciters_embeddings.npy", allow_pickle=True).item()
print(f"✅ Loaded {len(reciters_embeddings)} reciters.\n")

def identify_reciter(file_path, top_k=3):
    """Find most similar reciters to input audio."""
    emb = compute_embedding(file_path)
    emb = emb / np.linalg.norm(emb)

    similarities = []
    for reciter, rec_emb in reciters_embeddings.items():
        rec_emb = rec_emb / np.linalg.norm(rec_emb)
        sim = 1 - cosine(emb, rec_emb)
        similarities.append((reciter, sim))

    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:top_k]

if __name__ == "__main__":
    matches = identify_reciter("sample_input.wav")
    for name, score in matches:
        print(f"{name}: {score:.4f}")
