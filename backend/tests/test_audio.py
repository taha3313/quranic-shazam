"""Audio decode behavior: soundfile path, ffmpeg fallback, garbage handling."""

from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from app.core.audio import decode_upload_bytes, load_audio_file


def test_decode_wav_returns_16k_mono(wav_bytes):
    waveform, sr = decode_upload_bytes(wav_bytes)
    assert sr == 16000
    assert waveform.ndim == 2 and waveform.shape[0] == 1


def test_decode_garbage_raises_valueerror():
    with pytest.raises(ValueError):
        decode_upload_bytes(b"\x00\x01\x02 not audio at all")


def test_decode_truncated_wav_raises():
    with pytest.raises(ValueError):
        decode_upload_bytes(b"RIFF")
    with pytest.raises(ValueError):
        decode_upload_bytes(b"")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_decode_webm_via_ffmpeg():
    # Generate a real webm/opus blob with the ffmpeg binary.
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.5",
            "-c:a",
            "libopus",
            "-f",
            "webm",
            "pipe:1",
        ],
        capture_output=True,
        timeout=15,
        check=True,
    )
    assert proc.stdout
    waveform, sr = decode_upload_bytes(proc.stdout)
    assert sr == 16000
    assert waveform.shape[1] >= 16000 * 0.4  # most of the 0.5 s survives


def test_load_audio_file_roundtrip(tmp_path, wav_bytes):
    path = tmp_path / "a.wav"
    path.write_bytes(wav_bytes)
    waveform, sr = load_audio_file(path)
    assert sr == 16000
    assert waveform.dtype == np.float32


def test_load_audio_file_missing_raises(tmp_path):
    with pytest.raises(Exception):  # noqa: B017 - libsndfile error type varies
        load_audio_file(tmp_path / "missing.wav")


def test_resample_stereo_to_16k():
    import io

    import soundfile as sf

    sr = 48000
    t = np.arange(sr, dtype=np.float32) / sr
    sine = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    stereo = np.stack([sine, sine * 0.5], axis=1)
    buf = io.BytesIO()
    sf.write(buf, stereo, sr, format="WAV", subtype="FLOAT")
    waveform, decoded_sr = decode_upload_bytes(buf.getvalue())
    assert decoded_sr == 16000
    assert waveform.shape == (1, 16000)
    assert waveform.dtype == np.float32
    assert np.isfinite(waveform).all()
    expected = 0.75 * np.sin(2 * np.pi * 440 * np.arange(16000) / 16000)
    np.testing.assert_allclose(waveform[0, 20:-20], expected[20:-20], atol=0.002)
