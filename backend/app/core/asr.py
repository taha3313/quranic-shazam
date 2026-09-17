"""Lazy faster-whisper ASR singleton for Quranic transcription.

Uses the CTranslate2 build of tarteel-ai/whisper-base-ar-quran
(OdyAsh/faster-whisper-base-ar-quran) for CPU inference. The model is
intentionally NOT loaded at import time (same policy as embeddings.py).
"""

from __future__ import annotations

import logging
import threading

import numpy as np
import torch

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_model = None


def get_model():
    """Return the shared WhisperModel, loading it once (thread-safe)."""
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is not None:
            return _model
        from faster_whisper import WhisperModel

        settings = get_settings()
        logger.info(
            "Loading ASR model %s on %s ...", settings.asr_model_source, settings.asr_device
        )
        _model = WhisperModel(
            settings.asr_model_source,
            device=settings.asr_device,
            compute_type=settings.asr_compute_type,
        )
        logger.info("ASR model loaded.")
        return _model


def is_loaded() -> bool:
    return _model is not None


def transcribe_waveform(waveform: torch.Tensor) -> tuple[str, list[dict]]:
    """Transcribe a 16 kHz mono waveform → (text, word list).

    Words are dicts with keys ``word``, ``start``, ``end`` (seconds).
    """
    audio = waveform.squeeze().detach().cpu().numpy().astype(np.float32)
    model = get_model()
    segments, _info = model.transcribe(
        audio,
        language="ar",
        word_timestamps=True,
        vad_filter=False,
        beam_size=5,
    )
    words: list[dict] = []
    texts: list[str] = []
    for seg in segments:
        texts.append(seg.text)
        if seg.words:
            for w in seg.words:
                words.append({"word": w.word, "start": w.start, "end": w.end})
    return " ".join(t.strip() for t in texts if t.strip()), words
