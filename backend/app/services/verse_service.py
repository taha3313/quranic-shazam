"""Verse identification: upload bytes → ASR transcript → surah/ayah matches."""

from __future__ import annotations

import logging
import threading

import torch

from app.core.arabic_norm import normalize_words
from app.core.asr import transcribe_waveform
from app.core.audio import decode_upload_bytes
from app.core.config import get_settings
from app.core.verse_match import VerseIndex, load_corpus

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_index: VerseIndex | None = None
# ASR inference must not run concurrently on one CPU box (same policy as
# the reciter service semaphore).
_infer_sem = threading.Semaphore(1)


def get_index() -> VerseIndex:
    """Load the verse corpus once; raise FileNotFoundError if missing."""
    global _index
    if _index is not None:
        return _index
    with _lock:
        if _index is not None:
            return _index
        settings = get_settings()
        if not settings.verse_corpus_path.exists():
            raise FileNotFoundError(
                "Verse corpus not found. Run: uv run python scripts/build_verse_corpus.py"
            )
        verses, names = load_corpus(settings.verse_corpus_path)
        _index = VerseIndex(verses, names)
        logger.info("Loaded %d verses from %s", len(verses), settings.verse_corpus_path)
        return _index


def reload_index() -> VerseIndex:
    global _index
    with _lock:
        _index = None
    return get_index()


def identify_transcript(
    transcript: str, top_k: int, index: VerseIndex | None = None
) -> list[dict]:
    """Pure-text path: normalized transcript → ranked verse matches (dicts)."""
    index = index or get_index()
    words = normalize_words(transcript)
    matches = index.identify(words, top_k=top_k)
    return [m.as_dict() for m in matches]


def identify_waveform(waveform: torch.Tensor, top_k: int) -> tuple[str, list[dict]]:
    """Blocking ASR + matching; run off the event loop via to_thread."""
    transcript, _words = transcribe_waveform(waveform)
    return transcript, identify_transcript(transcript, top_k)


def identify_upload_bytes(data: bytes, top_k: int) -> tuple[str, list[dict]]:
    """Blocking identify, bounded by the inference semaphore.

    Callers on the asyncio loop MUST run this via anyio.to_thread (the
    route does); it must never execute on the event loop itself.
    """
    settings = get_settings()
    waveform, _sr = decode_upload_bytes(data, target_sr=settings.sample_rate)
    max_samples = settings.verse_max_audio_sec * settings.sample_rate
    if waveform.shape[1] > max_samples:
        waveform = waveform[:, :max_samples]
    with _infer_sem:
        return identify_waveform(waveform, top_k)


def is_confident(matches: list[dict]) -> bool:
    """Require both evidence and separation from competing locations."""
    settings = get_settings()
    return (
        bool(matches)
        and matches[0]["score"] >= settings.verse_score_threshold
        and matches[0]["words_matched"] >= 2
        and matches[0]["words_matched"] / max(1, matches[0]["words_total"]) >= 0.6
        and (len(matches) < 2 or matches[0]["score"] - matches[1]["score"] >= 0.05)
    )


def identify_progressive_bytes(data: bytes, top_k: int) -> dict:
    """Use additional audio only while the verse location remains uncertain.

    Decode one cumulative browser recording. Transcribe bounded windows
    independently and match their combined context; never truncate every
    retry back to the same first 20 seconds.
    """
    settings = get_settings()
    waveform, _ = decode_upload_bytes(data, target_sr=settings.sample_rate)
    limit = settings.verse_listen_max_sec * settings.sample_rate
    waveform = waveform[:, :limit]
    step = settings.verse_listen_step_sec * settings.sample_rate
    transcripts: list[str] = []
    matches: list[dict] = []
    processed = 0
    with _infer_sem:
        for start in range(0, waveform.shape[1], step):
            end = min(start + step, waveform.shape[1])
            # A very short trailing fragment adds little useful context.
            if end - start < settings.sample_rate and transcripts:
                break
            text, _ = transcribe_waveform(waveform[:, start:end])
            if text.strip():
                transcripts.append(text.strip())
            processed = end
            matches = identify_transcript(" ".join(transcripts), max(top_k, 2))
            if is_confident(matches):
                break
    confident = is_confident(matches)
    reached_limit = waveform.shape[1] >= limit
    return {
        "transcript": " ".join(transcripts),
        "matches": matches,
        "confident": confident,
        "needs_more_audio": not confident and not reached_limit,
        "listen_limit_reached": not confident and reached_limit,
        "audio_seconds": processed / settings.sample_rate,
    }
