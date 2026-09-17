"""API contract tests for POST /identify_verse (ASR stubbed)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_FAKE_MATCHES = [
    {
        "surah": 1,
        "surah_name": "الفاتحه",
        "ayah_start": 2,
        "ayah_end": 4,
        "score": 0.95,
        "words_matched": 9,
        "words_total": 9,
        "text": "الحمد لله رب العالمين",
    },
    {
        "surah": 37,
        "surah_name": "الصافات",
        "ayah_start": 182,
        "ayah_end": 182,
        "score": 0.61,
        "words_matched": 3,
        "words_total": 9,
        "text": "والحمد لله رب العالمين",
    },
]


def _stub_identify(monkeypatch, matches=None, transcript="الحمد لله"):
    from app.services import verse_service

    def fake(data: bytes, top_k: int):
        return transcript, list(matches if matches is not None else _FAKE_MATCHES)

    monkeypatch.setattr(verse_service, "identify_upload_bytes", fake)


def test_identify_verse_happy_path(wav_bytes, monkeypatch):
    _stub_identify(monkeypatch)
    resp = client.post("/identify_verse", files={"file": ("clip.wav", wav_bytes, "audio/wav")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["confident"] is True
    assert body["transcript"] is None  # hidden by default
    top = body["matches"][0]
    assert top["surah"] == 1 and top["ayah_start"] == 2 and top["ayah_end"] == 4
    assert top["surah_name"] == "الفاتحه"


def test_identify_verse_transcript_opt_in(wav_bytes, monkeypatch):
    _stub_identify(monkeypatch)
    resp = client.post(
        "/identify_verse",
        files={"file": ("clip.wav", wav_bytes, "audio/wav")},
        params={"include_transcript": True},
    )
    assert resp.json()["transcript"] == "الحمد لله"


def test_identify_verse_not_confident(wav_bytes, monkeypatch):
    low = [dict(_FAKE_MATCHES[1], score=0.2)]
    _stub_identify(monkeypatch, matches=low)
    resp = client.post("/identify_verse", files={"file": ("clip.wav", wav_bytes, "audio/wav")})
    body = resp.json()
    assert body["confident"] is False
    assert body["matches"][0]["score"] == 0.2


def test_identify_verse_empty_file(wav_bytes, monkeypatch):
    _stub_identify(monkeypatch)
    resp = client.post("/identify_verse", files={"file": ("e.wav", b"", "audio/wav")})
    assert resp.status_code == 400


def test_identify_verse_top_k_bounds(wav_bytes, monkeypatch):
    _stub_identify(monkeypatch)
    assert (
        client.post(
            "/identify_verse",
            files={"file": ("c.wav", wav_bytes, "audio/wav")},
            params={"top_k": 0},
        ).status_code
        == 422
    )


def test_identify_verse_missing_corpus_503(wav_bytes, monkeypatch):
    from app.services import verse_service

    def fake_missing(data: bytes, top_k: int):
        raise FileNotFoundError("corpus missing")

    monkeypatch.setattr(verse_service, "identify_upload_bytes", fake_missing)
    resp = client.post("/identify_verse", files={"file": ("c.wav", wav_bytes, "audio/wav")})
    assert resp.status_code == 503


def test_ambiguous_match_not_confident_even_with_top_k_one(wav_bytes, monkeypatch):
    tied = [dict(_FAKE_MATCHES[0]), dict(_FAKE_MATCHES[0], ayah_start=5, ayah_end=5)]
    _stub_identify(monkeypatch, matches=tied)
    resp = client.post(
        "/identify_verse?top_k=1",
        files={"file": ("clip.wav", wav_bytes, "audio/wav")},
    )
    assert resp.status_code == 200
    assert resp.json()["confident"] is False
    assert len(resp.json()["matches"]) == 1


def test_progressive_api_preserves_listening_status(wav_bytes, monkeypatch):
    from app.services import verse_service

    def fake(data, top_k):
        assert top_k == 1
        return {
            "transcript": "more context",
            "matches": _FAKE_MATCHES,
            "confident": False,
            "needs_more_audio": True,
            "listen_limit_reached": False,
            "audio_seconds": 8.0,
        }

    monkeypatch.setattr(verse_service, "identify_progressive_bytes", fake)
    resp = client.post(
        "/identify_verse_progressive?top_k=1",
        files={"file": ("clip.wav", wav_bytes, "audio/wav")},
    )
    assert resp.status_code == 200
    result = resp.json()
    assert result["transcript"] is None
    assert result["needs_more_audio"]
    assert result["audio_seconds"] == 8
    assert len(result["matches"]) == 1
