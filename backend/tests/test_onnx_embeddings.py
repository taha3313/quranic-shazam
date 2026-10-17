"""Runtime and input contract regressions for the exported reciter model."""

from __future__ import annotations

import subprocess
import sys

import numpy as np
import pytest

from app.core import embeddings
from app.core.config import get_settings


def test_runtime_import_does_not_load_torch():
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from app.main import app; "
            "assert not {'torch', 'torchaudio', 'speechbrain'} & set(sys.modules)",
        ],
        check=True,
        timeout=20,
    )


def test_missing_artifact_explains_export_command(monkeypatch, tmp_path):
    monkeypatch.setattr(embeddings, "_classifier", None)
    monkeypatch.setattr(get_settings(), "reciter_onnx_path", tmp_path / "missing.onnx")
    with pytest.raises(FileNotFoundError, match="scripts.export_reciter_onnx"):
        embeddings.get_classifier()


def test_spectrogram_dynamic_lengths_and_silence():
    for samples in (16000, 80000, 480000):
        power = embeddings.power_spectrogram(np.zeros((1, samples), dtype=np.float32))
        assert power.shape == (1, samples // 160 + 1, 201)
        assert power.dtype == np.float32
        assert np.all(power == 0)


def test_wrong_sample_rate_is_rejected():
    with pytest.raises(ValueError, match="16000 Hz"):
        embeddings.embedding_from_waveform(np.zeros((1, 8000), dtype=np.float32), 8000)


def test_exported_model_accepts_variable_lengths():
    if not get_settings().reciter_onnx_path.is_file():
        pytest.skip("Exported model not present; run export_reciter_onnx for integration check")
    rng = np.random.default_rng(42)
    for seconds in (1, 5):
        waveform = rng.normal(0, 0.1, (1, seconds * 16000)).astype(np.float32)
        vector = embeddings.embedding_from_waveform(waveform)
        assert vector.shape == (192,)
        assert np.isfinite(vector).all()
