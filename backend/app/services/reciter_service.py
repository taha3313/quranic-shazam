"""Loads the precomputed reciter embedding DB once and ranks queries."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import numpy as np
import torch

from app.core.audio import decode_upload_bytes
from app.core.config import get_settings
from app.core.embeddings import embedding_from_waveform
from app.core.similarity import rank_reciters

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_db: dict[str, np.ndarray] | None = None
_display_names: dict[str, str] = {}
# CPU inference does not parallelize (torch uses all cores per call); the
# semaphore just prevents N concurrent requests from thrashing the machine.
_infer_sem = threading.Semaphore(2)


def get_database() -> dict[str, np.ndarray]:
    """Load ``reciters_embeddings.npy`` once; return {} with a warning if missing."""
    global _db
    if _db is not None:
        return _db
    with _lock:
        if _db is not None:
            return _db
        settings = get_settings()
        path: Path = settings.embeddings_path
        if not path.exists():
            logger.warning("Embeddings file not found at %s. Run: make embeddings", path)
            _db = {}
            return _db
        try:
            raw = np.load(str(path), allow_pickle=True)
            _db = raw.item() if raw.size == 1 else dict(raw)
            logger.info("Loaded %d reciter embeddings from %s", len(_db), path)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to load embeddings from %s: %s", path, exc)
            _db = {}
        _load_display_names()
        return _db


def _load_display_names() -> None:
    """Load key → display name from data/reciters.json (optional file)."""
    global _display_names
    settings = get_settings()
    path = settings.data_dir / "reciters.json"
    try:
        import json

        entries = json.loads(path.read_text())["reciters"]
        _display_names = {
            e["key"]: e["name"] for e in entries if e.get("key") and e.get("name")
        }
    except Exception as exc:  # noqa: BLE001 - metadata is optional
        logger.warning("Could not load reciter metadata from %s: %s", path, exc)
        _display_names = {}


def reload_database() -> dict[str, np.ndarray]:
    global _db
    with _lock:
        _db = None
    return get_database()


def identify_waveform(waveform: torch.Tensor, sr: int, top_k: int) -> list[dict[str, float]]:
    db = get_database()
    if not db:
        raise FileNotFoundError(
            "No reciter embeddings loaded. Generate them first (make embeddings)."
        )
    query = embedding_from_waveform(waveform, sr)
    return rank_reciters(query, db, top_k=top_k, display_names=_display_names)


def identify_upload_bytes(data: bytes, top_k: int) -> list[dict[str, float]]:
    """Blocking identify, bounded by the inference semaphore.

    Callers on the asyncio loop MUST run this via anyio.to_thread (the
    routes do); it must never execute on the event loop itself.
    """
    settings = get_settings()
    waveform, sr = decode_upload_bytes(data, target_sr=settings.sample_rate)
    max_samples = settings.max_audio_sec * settings.sample_rate
    if waveform.shape[1] > max_samples:
        waveform = waveform[:, :max_samples]
    with _infer_sem:
        return identify_waveform(waveform, sr, top_k=top_k)
