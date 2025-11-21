import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from scipy.spatial.distance import cosine
from extract_embeddings import compute_embedding_chunk  # we create this

router = APIRouter()

reciters_embeddings = np.load("data/reciters_embeddings.npy", allow_pickle=True).item()


router = APIRouter()

# load reciter embeddings
reciters_embeddings = np.load(
    "data/reciters_embeddings.npy", allow_pickle=True
).item()


def get_top_matches(emb):
    """Return sorted similarity list."""
    emb = emb / np.linalg.norm(emb)
    similarities = []

    for reciter, rec_emb in reciters_embeddings.items():
        rec_emb = rec_emb / np.linalg.norm(rec_emb)
        sim = 1 - cosine(emb, rec_emb)
        similarities.append((reciter, float(sim)))

    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[:3]



# --------------------------------------------
# Live WebSocket endpoint
# --------------------------------------------
@router.websocket("/live_reciter")
async def live_recognize(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            chunk = await websocket.receive_bytes()
            print(f"Received chunk of size: {len(chunk)} bytes")
            emb = compute_embedding_chunk(chunk)
            if emb is None:
                print("Invalid chunk received.")
                # silently ignore invalid chunk
                continue

            best = get_top_matches(emb)
            await websocket.send_json({"matches": best})

    except WebSocketDisconnect:
        print("Client disconnected")