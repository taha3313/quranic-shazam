import numpy as np
from fastapi import APIRouter, UploadFile, File, HTTPException
from scipy.spatial.distance import cosine
from extract_embeddings import compute_embedding  # same function you tested

router = APIRouter()

# Load embeddings once
try:
    reciters_embeddings = np.load("data/reciters_embeddings.npy", allow_pickle=True).item()
    print(f"Loaded {len(reciters_embeddings)} reciters embeddings.")
except Exception as e:
    print("Error loading embeddings:", e)
    reciters_embeddings = {}

@router.post("/identify_reciter")
async def identify_reciter(file: UploadFile = File(...), top_k: int = 3):
    if not file:
        raise HTTPException(status_code=400, detail="Audio file is required.")

    try:
        # Save uploaded audio to a temporary file
        contents = await file.read()
        temp_path = f"temp_{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(contents)

        # Compute embedding using your old working code
        emb = compute_embedding(temp_path)
        emb = emb / np.linalg.norm(emb)

        similarities = []
        for reciter, rec_emb in reciters_embeddings.items():
            rec_emb = rec_emb / np.linalg.norm(rec_emb)
            sim = 1 - cosine(emb, rec_emb)
            similarities.append({"reciter": reciter, "score": float(sim)})

        # Sort by similarity
        similarities = sorted(similarities, key=lambda x: x["score"], reverse=True)

        # Return top-k
        return {"matches": similarities[:top_k]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
