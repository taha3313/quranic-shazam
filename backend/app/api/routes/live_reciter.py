"""WebSocket /live_reciter — sliding-window live reciter recognition.

Client streams binary audio chunks (webm/opus from MediaRecorder or raw wav).
Server accumulates ~``live_window_sec`` of audio, runs one embedding, and
replies with the top matches once the confidence threshold is reached.
"""

from __future__ import annotations

import logging

import torch
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.schemas import IdentifyResponse, ReciterMatch
from app.core.audio import decode_upload_bytes, normalize
from app.core.config import get_settings
from app.services import reciter_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["live"])


@router.websocket("/live_reciter")
async def live_reciter(ws: WebSocket):
    await ws.accept()
    settings = get_settings()

    chunks: list[torch.Tensor] = []
    buffered_sec = 0.0

    try:
        while True:
            try:
                data: bytes = await ws.receive_bytes()
            except WebSocketDisconnect:
                logger.info("live_reciter: client disconnected")
                break

            if not data:
                continue

            try:
                waveform, sr = decode_upload_bytes(data, target_sr=settings.sample_rate)
            except ValueError as exc:
                await ws.send_json({"error": str(exc)})
                continue

            chunks.append(normalize(waveform))
            buffered_sec += waveform.shape[1] / settings.sample_rate

            if buffered_sec < settings.live_window_sec:
                continue

            merged = torch.cat([c.reshape(1, -1) for c in chunks], dim=1)
            try:
                matches = reciter_service.identify_waveform(
                    merged, settings.sample_rate, top_k=3
                )
            except FileNotFoundError as exc:
                await ws.send_json({"error": str(exc)})
                break
            except Exception:  # noqa: BLE001
                logger.exception("live embedding failed")
                await ws.send_json({"error": "Embedding failed."})
                chunks, buffered_sec = [], 0.0
                continue

            if not matches:
                await ws.send_json({"error": "No reciters in database."})
                break

            if matches[0]["score"] >= settings.live_confidence_threshold:
                payload = IdentifyResponse(
                    matches=[ReciterMatch(**m) for m in matches]
                ).model_dump()
                await ws.send_json(payload)
                chunks, buffered_sec = [], 0.0
            elif buffered_sec >= settings.live_max_duration_sec:
                await ws.send_json(
                    {"matches": [{"reciter": "Not sure", "score": 0.0}]}
                )
                break
            # else: keep accumulating for the next window
    except WebSocketDisconnect:
        logger.info("live_reciter: client disconnected")
    except Exception as exc:  # noqa: BLE001
        logger.exception("live_reciter crashed")
        try:
            await ws.send_json({"error": str(exc)})
        except Exception:
            pass
