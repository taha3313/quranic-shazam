"""WebSocket /live_reciter — sliding-window live reciter recognition.

Client streams binary audio chunks. Two chunk shapes are supported:

- **Container streams** (webm/opus from MediaRecorder): only the first
  chunk carries the container header, so the server decodes the *whole*
  accumulated byte buffer cumulatively; a consumed-samples offset marks
  what has already been identified.
- **Self-contained chunks** (raw wav frames): cumulative decode of the
  concatenation fails, so each chunk is decoded individually.

Decoding and inference run in worker threads (never on the event loop).
"""

from __future__ import annotations

import functools
import logging

import anyio.to_thread
import torch
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.schemas import IdentifyResponse, ReciterMatch
from app.core.audio import decode_upload_bytes, normalize
from app.core.config import get_settings
from app.services import reciter_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["live"])

# Decode the accumulated buffer at most every N chunks (~300 ms each).
_DECODE_EVERY_CHUNKS = 3
# Hard cap on the raw byte buffer (headers must be preserved for webm).
_RAW_BUFFER_CAP = 10_000_000


def _decode_step(
    raw_all: bytes, pending: list[bytes], target_sr: int
) -> tuple[str, object, int]:
    """Decode in a worker thread; returns (mode, payload, error_count).

    Decode recognized webm containers cumulatively, waiting for more
    bytes when the header is incomplete. Otherwise prefer self-contained
    chunks such as wav, falling back to cumulative decoding when all fail.

    mode "cum": payload is the full decoded session waveform.
    mode "chunk": payload is a list of per-chunk waveforms.
    """
    # Browser webm fragments share one header. Even the first fragment
    # may contain only an incomplete container: wait for more bytes.
    if raw_all.startswith(b"\x1a\x45\xdf\xa3"):
        try:
            waveform, _ = decode_upload_bytes(raw_all, target_sr=target_sr)
            return "cum", normalize(waveform), 0
        except ValueError:
            return "pending", None, 0

    tensors: list[torch.Tensor] = []
    errors = 0
    for chunk in pending:
        try:
            waveform, _ = decode_upload_bytes(chunk, target_sr=target_sr)
            tensors.append(normalize(waveform))
        except ValueError:
            errors += 1
    if tensors or not errors:
        return "chunk", tensors, errors
    try:
        waveform, _ = decode_upload_bytes(raw_all, target_sr=target_sr)
        return "cum", normalize(waveform), 0
    except ValueError:
        return "chunk", [], errors


@router.websocket("/live_reciter")
async def live_reciter(ws: WebSocket):
    await ws.accept()
    settings = get_settings()
    sr = settings.sample_rate

    raw_all = bytearray()
    pending: list[bytes] = []
    chunks_since_decode = 0

    session: torch.Tensor | None = None  # "cum" mode: full decoded audio
    consumed = 0                         # samples already identified
    waveforms: list[torch.Tensor] = []   # "chunk" mode
    identified_samples = 0               # chunk-mode samples already identified

    def buffered_sec() -> float:
        if session is not None:
            return max((session.shape[1] - consumed) / sr, 0.0)
        return sum(w.shape[1] for w in waveforms) / sr

    def window_waveform() -> torch.Tensor | None:
        if session is not None:
            return session[:, consumed:]
        if waveforms:
            return torch.cat([w.reshape(1, -1) for w in waveforms], dim=1)
        return None

    async def send_matches(matches: list[dict]) -> None:
        payload = IdentifyResponse(
            matches=[ReciterMatch(**m) for m in matches]
        ).model_dump()
        await ws.send_json(payload)

    try:
        while True:
            try:
                data: bytes = await ws.receive_bytes()
            except WebSocketDisconnect:
                logger.info("live_reciter: client disconnected")
                break

            if not data:
                continue
            if len(raw_all) < _RAW_BUFFER_CAP:
                raw_all.extend(data)
            pending.append(data)
            chunks_since_decode += 1

            decoded_yet = session is not None or waveforms
            if decoded_yet and chunks_since_decode < _DECODE_EVERY_CHUNKS:
                continue

            chunks_since_decode = 0
            try:
                mode, payload, errors = await anyio.to_thread.run_sync(
                    functools.partial(
                        _decode_step, bytes(raw_all), list(pending), sr
                    )
                )
            except Exception:  # noqa: BLE001
                logger.exception("live decode crashed")
                await ws.send_json({"error": "Decode failed."})
                continue

            if mode == "pending":
                pending.clear()
                continue
            if mode == "cum":
                session = payload
                # Waveforms decoded before the switch are part of the
                # session's timeline but have already been identified.
                consumed = identified_samples
                pending.clear()
            else:
                waveforms.extend(payload)
                pending.clear()
                if not waveforms and errors:
                    await ws.send_json({"error": "Could not decode audio chunk."})
                    continue

            if buffered_sec() < settings.live_window_sec:
                continue

            merged = window_waveform()
            try:
                matches = await anyio.to_thread.run_sync(
                    functools.partial(
                        reciter_service.identify_waveform,
                        merged,
                        sr,
                        top_k=3,
                    )
                )
            except FileNotFoundError as exc:
                await ws.send_json({"error": str(exc)})
                break
            except Exception:  # noqa: BLE001
                logger.exception("live embedding failed")
                await ws.send_json({"error": "Embedding failed."})
                # Skip the broken window instead of retrying it forever.
                if session is not None:
                    consumed = session.shape[1]
                else:
                    identified_samples += sum(w.shape[1] for w in waveforms)
                    waveforms = []
                continue

            if not matches:
                await ws.send_json({"error": "No reciters in database."})
                break

            if matches[0]["score"] >= settings.live_confidence_threshold:
                await send_matches(matches)
                if session is not None:
                    consumed = session.shape[1]
                else:
                    identified_samples += sum(w.shape[1] for w in waveforms)
                    waveforms = []
            elif buffered_sec() >= settings.live_max_duration_sec:
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
