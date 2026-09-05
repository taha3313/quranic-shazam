"""Lazy SpeechBrain embedding model + helpers.

The model is intentionally NOT loaded at import time so that:
- ``uvicorn --reload`` / tests / CLI scripts import fast,
- a missing model cache fails loudly only when actually needed.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import numpy as np
import torch

from app.core.audio import ensure_min_length, load_audio_file, normalize, resample
from app.core.config import get_settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_classifier = None


def get_classifier():
    """Return the shared EncoderClassifier, loading it once (thread-safe)."""
    global _classifier
    if _classifier is not None:
        return _classifier
    with _lock:
        if _classifier is not None:
            return _classifier
        from speechbrain.pretrained import EncoderClassifier

        settings = get_settings()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info("Loading embedding model %s on %s ...", settings.embedding_model_source, device)
        _classifier = EncoderClassifier.from_hparams(
            source=settings.embedding_model_source,
            run_opts={"device": device},
        )
        logger.info("Embedding model loaded.")
        return _classifier


@torch.no_grad()
def embedding_from_waveform(waveform: torch.Tensor, sr: int = 16000) -> np.ndarray:
    """Compute an embedding from an in-memory waveform tensor."""
    settings = get_settings()
    waveform = resample(normalize(waveform), sr, settings.sample_rate)
    waveform = ensure_min_length(waveform, min_samples=settings.sample_rate)
    classifier = get_classifier()
    emb = classifier.encode_batch(waveform).squeeze().detach().cpu().numpy()
    return np.asarray(emb)


def embedding_from_file(path: str | Path) -> np.ndarray:
    """Compute an embedding from an audio file on disk."""
    waveform, sr = load_audio_file(path)
    return embedding_from_waveform(waveform, sr)
