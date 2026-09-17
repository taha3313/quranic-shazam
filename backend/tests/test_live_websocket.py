"""WebSocket /live_reciter protocol tests (embedding fn stubbed)."""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _wav_chunk(seconds: float = 3.0) -> bytes:
    import io

    import numpy as np
    import soundfile as sf

    buf = io.BytesIO()
    sf.write(buf, np.zeros(int(16000 * seconds), dtype="float32"), 16000, format="wav")
    return buf.getvalue()


def test_live_error_frame_on_garbage(fake_env):
    with client.websocket_connect("/live_reciter") as ws:
        ws.send_bytes(b"\x00\x01 not audio")
        msg = ws.receive_json()
        assert "error" in msg


def test_live_result_frame_shape(fake_env):
    db, queries = fake_env
    with client.websocket_connect("/live_reciter") as ws:
        # One 6 s chunk exceeds the 5 s window -> triggers identification.
        ws.send_bytes(_wav_chunk(6.0))
        msg = ws.receive_json()
        assert "matches" in msg
        assert msg["matches"][0]["reciter"] == "alpha"


def test_live_no_identify_below_window(fake_env):
    """Below the 5 s window the server stays silent, yet stays alive:
    appending garbage (which ffmpeg tolerates by dropping) and then
    enough audio to reach the window still yields a single result."""
    with client.websocket_connect("/live_reciter") as ws:
        ws.send_bytes(_wav_chunk(1.0))
        ws.send_bytes(b"garbage")  # tolerated/dropped, no frame expected
        ws.send_bytes(_wav_chunk(4.5))  # decode trigger is every 3 chunks
        ws.send_bytes(_wav_chunk(4.5))  # total 5.5 s decoded -> identify
        msg = ws.receive_json()
        assert "matches" in msg, f"expected result, got {msg}"
        assert msg["matches"][0]["reciter"] == "alpha"


def test_live_max_duration_not_sure(fake_env, monkeypatch):
    from app.core.config import get_settings

    db, queries = fake_env
    queries["vector"] = np.array([0.0, 0.0, 1.0])  # orthogonal: low score
    settings = get_settings()
    monkeypatch.setattr(settings, "live_max_duration_sec", 5.0)
    with client.websocket_connect("/live_reciter") as ws:
        # 6 s chunk: window (5 s) reached -> identify -> score below
        # threshold -> buffered (6 s) >= max (5 s) -> "Not sure".
        ws.send_bytes(_wav_chunk(6.0))
        msg = ws.receive_json()
        assert msg["matches"][0]["reciter"] == "Not sure"


def test_live_disconnect_is_clean(fake_env):
    with client.websocket_connect("/live_reciter") as ws:
        ws.send_bytes(_wav_chunk(1.0))
    # Context exit closes the socket; no server-side exception means the
    # test suite still passes afterwards (other endpoints respond).
    resp = client.get("/health")
    assert resp.status_code == 200


def _webm_bytes(seconds: float = 6.0) -> bytes:
    """A real webm/opus stream of `seconds` length (ffmpeg-generated)."""
    import shutil
    import subprocess

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
         "-i", f"sine=frequency=440:duration={seconds}", "-c:a", "libopus",
         "-f", "webm", "pipe:1"],
        capture_output=True, timeout=30, check=True,
    )
    return proc.stdout


def test_live_webm_stream_identifies(fake_env):
    """C2 regression: webm chunks after the first have no header; the
    server must decode cumulatively instead of per-chunk."""
    raw = _webm_bytes(6.0)
    assert len(raw) > 2000
    parts = [raw[: len(raw) // 4]] + [
        raw[i : i + max(len(raw) // 8, 1)]
        for i in range(len(raw) // 4, len(raw), max(len(raw) // 8, 1))
    ]
    with client.websocket_connect("/live_reciter") as ws:
        for part in parts:
            ws.send_bytes(part)
        msg = ws.receive_json()
        assert "matches" in msg, f"expected result, got {msg}"
        assert msg["matches"][0]["reciter"] == "alpha"


def test_live_incomplete_webm_header_waits_for_more(fake_env):
    raw = _webm_bytes(6.0)
    with client.websocket_connect("/live_reciter") as ws:
        ws.send_bytes(raw[:32])
        ws.send_bytes(raw[32:])
        msg = ws.receive_json()
        assert "matches" in msg, f"unexpected provisional decode error: {msg}"
        assert msg["matches"][0]["reciter"] == "alpha"
