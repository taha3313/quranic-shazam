# backend/app/routes/reciter.py
from fastapi import APIRouter, File, UploadFile, HTTPException
from app.core.audio_utils import load_audio_from_upload
from app.core.embeddings import get_embedding, load_reference_embeddings
from app.core.similarity import find_best_match

router = APIRouter()
reciters_db = load_reference_embeddings()  # loads real embeddings built earlier

@router.post("/identify_reciter")
async def identify_reciter(file: UploadFile = File(...)):
    if not file:
        raise HTTPException(status_code=400, detail="Audio file required.")
    try:
        waveform = load_audio_from_upload(await file.read())  # returns torch.Tensor shape [1, T]
        query_emb = get_embedding(waveform)
        match = find_best_match(query_emb, reciters_db)
        return match
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
