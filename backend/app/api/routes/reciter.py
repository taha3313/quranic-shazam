"""POST /identify_reciter — identify the reciter from an uploaded audio file."""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.api.schemas import IdentifyResponse, ReciterMatch
from app.core.config import get_settings
from app.services import reciter_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reciter"])


@router.post("/identify_reciter", response_model=IdentifyResponse)
async def identify_reciter(
    file: UploadFile = File(...),  # noqa: B008 - FastAPI idiom
    top_k: int = Query(default=3, ge=1, le=10),
):
    settings = get_settings()
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="Audio file is required.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {settings.max_upload_mb} MB).",
        )

    try:
        matches = reciter_service.identify_upload_bytes(data, top_k=top_k)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("identify_reciter failed for %s", file.filename)
        raise HTTPException(status_code=500, detail="Identification failed.") from exc

    return IdentifyResponse(matches=[ReciterMatch(**m) for m in matches])
