"""Audio loading / decoding helpers. All audio is normalized to 16 kHz mono float32."""

from __future__ import annotations

import io
import logging
import math
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

TARGET_SR = 16000


def to_mono(waveform: np.ndarray) -> np.ndarray:
    waveform = np.asarray(waveform, dtype=np.float32)
    if waveform.ndim == 1:
        return waveform[None, :]
    if waveform.ndim != 2:
        raise ValueError("Expected audio shaped (channels, samples).")
    return waveform.mean(axis=0, keepdims=True) if waveform.shape[0] > 1 else waveform


def normalize(waveform: np.ndarray) -> np.ndarray:
    return to_mono(waveform)


@lru_cache(maxsize=8)
def _sinc_kernel(down: int, up: int) -> tuple[np.ndarray, int]:
    """Six-lobe Hann-windowed sinc, matching torchaudio's default filter."""
    base = min(down, up) * 0.99
    width = math.ceil(6 * down / base)
    grid = np.arange(-width, width + down, dtype=np.float32) / np.float32(down)
    phases = -np.arange(up, dtype=np.float32) / np.float32(up)
    t = (phases[:, None] + grid[None, :]) * np.float32(base)
    t = np.clip(t, -6, 6)
    window = np.cos(t * np.float32(np.pi) / np.float32(6) / np.float32(2)) ** 2
    angle = t * np.float32(np.pi)
    sinc = np.ones_like(angle)
    np.divide(np.sin(angle), angle, out=sinc, where=angle != 0)
    return (sinc * (window * np.float32(base / down))).T.copy(), width


def resample(waveform: np.ndarray, orig_sr: int, target_sr: int = TARGET_SR) -> np.ndarray:
    if orig_sr == target_sr:
        return waveform
    divisor = math.gcd(orig_sr, target_sr)
    down, up = orig_sr // divisor, target_sr // divisor
    # Unusual coprime rates must not create an enormous phase-filter matrix.
    if down > 4096 or up > 1024:
        from scipy.signal import resample_poly

        return resample_poly(waveform, up, down, axis=-1).astype(np.float32)
    kernel, width = _sinc_kernel(down, up)
    padded = np.pad(waveform, ((0, 0), (width, width + down)))
    frames = np.lib.stride_tricks.sliding_window_view(padded, kernel.shape[0], axis=-1)
    result = (frames[:, ::down, :] @ kernel).reshape(waveform.shape[0], -1)
    count = math.ceil(waveform.shape[-1] * up / down)
    return result[:, :count].astype(np.float32)


def load_audio_file(path: str | Path, target_sr: int = TARGET_SR) -> tuple[np.ndarray, int]:
    return decode_upload_bytes(Path(path).read_bytes(), target_sr)


def decode_upload_bytes(
    data: bytes, target_sr: int = TARGET_SR, max_seconds: float | None = None
) -> tuple[np.ndarray, int]:
    """Decode soundfile formats directly, with FFmpeg for browser recordings."""
    import soundfile as sf

    if max_seconds is not None and max_seconds <= 0:
        raise ValueError("Audio duration limit must be positive.")

    def bounded(audio):
        if max_seconds is None:
            return audio
        return audio[:, : int(max_seconds * target_sr)].copy()

    try:
        with sf.SoundFile(io.BytesIO(data)) as source:
            sr = source.samplerate
            # Preserve resampler lookahead at the cutoff without decoding the
            # entire upload into memory before applying the service's limit.
            frames = -1 if max_seconds is None else math.ceil((max_seconds + 0.01) * sr)
            audio = source.read(frames=frames, dtype="float32", always_2d=True)
        return bounded(resample(normalize(audio.T), sr, target_sr)), target_sr
    except Exception as exc:  # noqa: BLE001 - FFmpeg supports additional formats
        logger.debug("soundfile decode failed (%s), trying ffmpeg", exc)
    decoded = _decode_with_ffmpeg(data, target_sr, max_seconds=max_seconds)
    if decoded is None:
        raise ValueError("Could not decode audio bytes (tried soundfile and ffmpeg).")
    audio, _ = sf.read(io.BytesIO(decoded), dtype="float32", always_2d=True)
    return bounded(normalize(audio.T)), target_sr


def _decode_with_ffmpeg(
    data: bytes, target_sr: int, timeout: int = 10, max_seconds: float | None = None
) -> bytes | None:
    """Use the ffmpeg binary to convert arbitrary audio bytes to wav bytes."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-ac",
        "1",
        "-ar",
        str(target_sr),
        "-f",
        "wav",
        "pipe:1",
    ]
    if max_seconds is not None:
        cmd[-3:-3] = ["-t", str(max_seconds + 0.01)]
    try:
        proc = subprocess.run(cmd, input=data, capture_output=True, timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        logger.warning("ffmpeg decode failed: %s", exc)
        return None
    if proc.returncode != 0 or not proc.stdout:
        logger.warning("ffmpeg decode failed: %s", proc.stderr.decode(errors="ignore")[:300])
        return None
    return proc.stdout


def ensure_min_length(
    waveform: np.ndarray, min_samples: int = TARGET_SR, sr: int = TARGET_SR
) -> np.ndarray:
    """Pad very short (<1s) chunks with tiny noise so the encoder doesn't crash."""
    waveform = normalize(waveform)
    if waveform.size >= min_samples:
        return waveform
    pad_len = min_samples - waveform.size
    pad = (1e-4 * np.random.default_rng().standard_normal((1, pad_len))).astype(np.float32)
    return np.concatenate([waveform.reshape(1, -1), pad], axis=1)


def save_upload_to_temp(data: bytes, suffix: str = ".wav") -> Path:
    """Persist uploaded bytes to a temp file; caller must unlink it."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(data)
        tmp.flush()
    finally:
        tmp.close()
    return Path(tmp.name)
