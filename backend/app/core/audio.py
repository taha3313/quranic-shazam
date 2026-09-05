"""Audio loading / decoding helpers. All audio is normalized to 16 kHz mono float32."""

from __future__ import annotations

import io
import logging
import subprocess
import tempfile
from pathlib import Path

import torch
import torchaudio

logger = logging.getLogger(__name__)

TARGET_SR = 16000


def to_mono(waveform: torch.Tensor) -> torch.Tensor:
    if waveform.dim() == 1:
        return waveform.unsqueeze(0)
    if waveform.size(0) > 1:
        return waveform.mean(dim=0, keepdim=True)
    return waveform


def resample(waveform: torch.Tensor, orig_sr: int, target_sr: int = TARGET_SR) -> torch.Tensor:
    if orig_sr == target_sr:
        return waveform
    return torchaudio.functional.resample(waveform, orig_freq=orig_sr, new_freq=target_sr)


def normalize(waveform: torch.Tensor) -> torch.Tensor:
    return to_mono(waveform.float())


def load_audio_file(path: str | Path, target_sr: int = TARGET_SR) -> tuple[torch.Tensor, int]:
    """Load an audio file from disk, normalized to mono `target_sr`.

    Uses soundfile (no torchcodec dependency); torchaudio is only a fallback
    for formats libsndfile cannot read.
    """
    try:
        import soundfile as sf

        data, sr = sf.read(str(path), dtype="float32", always_2d=True)
        waveform = torch.from_numpy(data.T)  # (channels, samples)
    except Exception as exc:  # noqa: BLE001
        logger.debug("soundfile failed (%s), falling back to torchaudio", exc)
        waveform, sr = torchaudio.load(str(path))
    waveform = resample(normalize(waveform), sr, target_sr)
    return waveform, target_sr


def decode_upload_bytes(data: bytes, target_sr: int = TARGET_SR) -> tuple[torch.Tensor, int]:
    """Decode uploaded audio bytes (mp3/wav/ogg/webm) to a mono waveform.

    Tries torchaudio first (works for wav/mp3), falls back to ffmpeg for
    browser MediaRecorder webm/opus chunks.
    """
    # Fast path: soundfile / torchaudio can read wav/mp3 from a buffer.
    try:
        import soundfile as sf

        data, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
        waveform = torch.from_numpy(data.T)
        return resample(normalize(waveform), sr, target_sr), target_sr
    except Exception as exc:  # noqa: BLE001 - fallback to ffmpeg
        logger.debug("soundfile direct decode failed (%s), trying ffmpeg", exc)

    ffmpeg_out = _decode_with_ffmpeg(data, target_sr)
    if ffmpeg_out is None:
        raise ValueError("Could not decode audio bytes (tried soundfile and ffmpeg).")
    import soundfile as sf

    data_out, _ = sf.read(io.BytesIO(ffmpeg_out), dtype="float32", always_2d=True)
    return normalize(torch.from_numpy(data_out.T)), target_sr


def _decode_with_ffmpeg(data: bytes, target_sr: int, timeout: int = 10) -> bytes | None:
    """Use the ffmpeg binary to convert arbitrary audio bytes to wav bytes."""
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-i", "pipe:0",
        "-ac", "1",
        "-ar", str(target_sr),
        "-f", "wav",
        "pipe:1",
    ]
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
    waveform: torch.Tensor, min_samples: int = TARGET_SR, sr: int = TARGET_SR
) -> torch.Tensor:
    """Pad very short (<1s) chunks with tiny noise so the encoder doesn't crash."""
    waveform = normalize(waveform)
    if waveform.numel() >= min_samples:
        return waveform
    pad_len = min_samples - waveform.numel()
    pad = 1e-4 * torch.randn(1, pad_len)
    return torch.cat([waveform.reshape(1, -1), pad], dim=1)


def save_upload_to_temp(data: bytes, suffix: str = ".wav") -> Path:
    """Persist uploaded bytes to a temp file; caller must unlink it."""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        tmp.write(data)
        tmp.flush()
    finally:
        tmp.close()
    return Path(tmp.name)
