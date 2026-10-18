"""Lazy ONNX reciter inference; no PyTorch or SpeechBrain runtime dependency."""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
from scipy.fft import rfft

from app.core.audio import ensure_min_length, load_audio_file, normalize
from app.core.config import get_settings
from app.core.memory import release_unused_memory

_lock = threading.Lock()
_classifier = None


def get_classifier():
    global _classifier
    if _classifier is not None:
        return _classifier
    with _lock:
        if _classifier is not None:
            return _classifier
        import onnxruntime as ort

        settings = get_settings()
        if not settings.reciter_onnx_path.is_file():
            raise FileNotFoundError(
                "Reciter ONNX model missing. Run: uv run --group export "
                "python -m scripts.export_reciter_onnx"
            )
        options = ort.SessionOptions()
        options.intra_op_num_threads = settings.inference_threads
        options.inter_op_num_threads = 1
        options.enable_cpu_mem_arena = False
        _classifier = ort.InferenceSession(
            str(settings.reciter_onnx_path), options, providers=["CPUExecutionProvider"]
        )
        if settings.low_memory:
            release_unused_memory()
        return _classifier


def release_model() -> None:
    global _classifier
    with _lock:
        _classifier = None


def is_loaded() -> bool:
    return _classifier is not None


def power_spectrogram(waveform: np.ndarray) -> np.ndarray:
    """SpeechBrain's centered 400-point periodic Hamming STFT, hop 160."""
    audio = normalize(waveform)
    audio = np.pad(audio, ((0, 0), (200, 200)), mode="constant")
    frames = np.lib.stride_tricks.sliding_window_view(audio, 400, axis=-1)[:, ::160, :]
    # Match torch.hamming_window's float32 arithmetic, not NumPy's symmetric window.
    phase = np.arange(400, dtype=np.float32) * np.float32(2 * np.pi / 400)
    window = np.float32(0.54) - np.float32(0.46) * np.cos(phase)
    spectrum = rfft(frames * window, axis=-1)
    return (spectrum.real**2 + spectrum.imag**2).astype(np.float32)


def embedding_from_waveform(waveform: np.ndarray, sr: int = 16000) -> np.ndarray:
    if sr != 16000:
        raise ValueError("Reciter model requires 16000 Hz audio.")
    audio = ensure_min_length(waveform, min_samples=16000)
    session = get_classifier()
    embedding = session.run(["embedding"], {"power": power_spectrogram(audio)})[0]
    return embedding.reshape(-1)


def embedding_from_file(path: str | Path) -> np.ndarray:
    waveform, sr = load_audio_file(path)
    return embedding_from_waveform(waveform, sr)
