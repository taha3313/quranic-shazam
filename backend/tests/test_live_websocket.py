"""WebSocket /live_reciter protocol tests (embedding fn stubbed)."""

from __future__ import annotations

import numpy as np
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
    with client.websocket_connect("/live_reciter") as ws:
        ws.send_bytes(_wav_chunk(1.0))
        # Server should stay silent; verify it is still responsive by
        # sending garbage and expecting an error frame (not a close).
        ws.send_bytes(b"garbage")
        msg = ws.receive_json()
        assert "error" in msg


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
