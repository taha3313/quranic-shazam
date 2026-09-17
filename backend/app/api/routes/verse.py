"""POST /identify_verse — identify surah + ayah from an uploaded recitation."""

from __future__ import annotations

import functools
import logging

import anyio.to_thread
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.api.routes.reciter import _read_capped
from app.api.schemas import IdentifyVerseResponse, VerseMatch
from app.core.config import get_settings
from app.services import verse_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["verse"])


@router.post("/identify_verse", response_model=IdentifyVerseResponse)
async def identify_verse(
    file: UploadFile = File(...),  # noqa: B008 - FastAPI idiom
    top_k: int = Query(default=3, ge=1, le=10),
    include_transcript: bool = Query(default=False),
):
    settings = get_settings()
    if file is None or not file.filename:
        raise HTTPException(status_code=400, detail="Audio file is required.")

    data = await _read_capped(file, settings.max_upload_bytes)
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        # ASR + matching are blocking CPU work: keep them off the event loop
        # (same policy as /identify_reciter).
        transcript, matches = await anyio.to_thread.run_sync(
            functools.partial(verse_service.identify_upload_bytes, data, max(top_k, 2))
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("identify_verse failed for %s", file.filename)
        raise HTTPException(status_code=500, detail="Verse identification failed.") from exc

    confident = verse_service.is_confident(matches)
    return IdentifyVerseResponse(
        transcript=transcript if include_transcript else None,
        confident=confident,
        needs_more_audio=not confident,
        matches=[VerseMatch(**m) for m in matches[:top_k]],
    )


@router.post("/identify_verse_progressive", response_model=IdentifyVerseResponse)
async def identify_verse_progressive(
    file: UploadFile = File(...),  # noqa: B008
    top_k: int = Query(default=3, ge=1, le=10),
    include_transcript: bool = Query(default=False),
):
    settings = get_settings()
    if not file.filename:
        raise HTTPException(status_code=400, detail="Audio file is required.")
    data = await _read_capped(file, settings.max_upload_bytes)
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    try:
        result = await anyio.to_thread.run_sync(
            functools.partial(verse_service.identify_progressive_bytes, data, top_k)
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Progressive verse identification failed")
        raise HTTPException(status_code=500, detail="Verse identification failed.") from exc
    result["matches"] = result["matches"][:top_k]
    if not include_transcript:
        result["transcript"] = None
    return IdentifyVerseResponse(**result)
