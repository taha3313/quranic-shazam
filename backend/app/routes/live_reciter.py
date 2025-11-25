import numpy as np
import asyncio
import torchaudio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from scipy.spatial.distance import cosine
from extract_embeddings import compute_embedding_live

router = APIRouter()

# Load reciters embeddings once
try:
    reciters_embeddings = np.load("data/reciters_embeddings.npy", allow_pickle=True).item()
    print(f"Loaded {len(reciters_embeddings)} reciters embeddings.")
except Exception as e:
    print("Error loading embeddings:", e)
    reciters_embeddings = {}

# Parameters
SLIDING_WINDOW_SEC = 5
SAMPLE_RATE = 16000  # adjust based on your model
CONFIDENCE_THRESHOLD = 0.85
MAX_DURATION_SEC = 30

@router.websocket("/live_reciter")
async def live_reciter(ws: WebSocket):
    await ws.accept()
    buffer = []
    total_seconds = 0
    try:
        while True:
            data = await ws.receive_bytes()
            # Convert bytes to waveform
            waveform, sr = torchaudio.load(data, format="webm")
            if sr != SAMPLE_RATE:
                waveform = torchaudio.functional.resample(waveform, sr, SAMPLE_RATE)
            buffer.append(waveform)
            total_seconds += waveform.shape[1] / SAMPLE_RATE

            # Check if enough audio for sliding window
            if total_seconds >= SLIDING_WINDOW_SEC:
                # Merge buffer into one waveform
                merged_waveform = np.concatenate([w.numpy() for w in buffer], axis=1)
                emb = compute_embedding_live(merged_waveform)
                emb = emb / np.linalg.norm(emb)

                similarities = []
                for reciter, rec_emb in reciters_embeddings.items():
                    rec_emb = rec_emb / np.linalg.norm(rec_emb)
                    sim = 1 - cosine(emb, rec_emb)
                    similarities.append({"reciter": reciter, "score": float(sim)})

                similarities = sorted(similarities, key=lambda x: x["score"], reverse=True)

                top_score = similarities[0]["score"]
                if top_score >= CONFIDENCE_THRESHOLD:
                    await ws.send_json({"matches": similarities[:3]})
                    buffer = []  # reset buffer after confident prediction
                    total_seconds = 0
                else:
                    # not confident yet, keep buffer for next window
                    if total_seconds >= MAX_DURATION_SEC:
                        await ws.send_json({"matches": [{"reciter": "Not sure", "score": 0}]})
                        break

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        await ws.send_json({"error": str(e)})
