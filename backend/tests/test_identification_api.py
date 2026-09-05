"""API contract tests for POST /identify_reciter (embedding fn stubbed)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _upload(wav_bytes, top_k="3"):
    return client.post(
        "/identify_reciter",
        files={"file": ("clip.wav", wav_bytes, "audio/wav")},
        params={"top_k": top_k},
    )


def test_identify_happy_path(fake_env, wav_bytes):
    resp = _upload(wav_bytes)
    assert resp.status_code == 200
    matches = resp.json()["matches"]
    assert matches, "expected at least one match"
    assert matches[0]["reciter"] == "alpha"
    assert matches[0]["score"] > matches[-1]["score"]


def test_identify_empty_file_rejected(fake_env):
    resp = client.post(
        "/identify_reciter", files={"file": ("empty.wav", b"", "audio/wav")}
    )
    assert resp.status_code == 400


def test_identify_oversize_rejected(fake_env, wav_bytes, monkeypatch):
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "max_upload_mb", 0)  # 0 MB limit
    resp = _upload(wav_bytes)
    assert resp.status_code == 413


def test_identify_garbage_bytes_rejected(fake_env):
    resp = _upload(b"\x00\x01\x02 not audio")
    assert resp.status_code == 400


def test_identify_missing_db_returns_503(wav_bytes, monkeypatch):
    from app.services import reciter_service

    monkeypatch.setattr(reciter_service, "_db", {})
    resp = _upload(wav_bytes)
    assert resp.status_code == 503


def test_top_k_bounds_enforced(fake_env, wav_bytes):
    assert _upload(wav_bytes, top_k="0").status_code == 422
    assert _upload(wav_bytes, top_k="99").status_code == 422
