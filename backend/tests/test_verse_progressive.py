"""Continued-listening regressions with the real verse corpus."""
from types import SimpleNamespace

import pytest
import torch

from app.services import verse_service


def setup_audio(monkeypatch, texts, seconds=24):
    settings = SimpleNamespace(
        sample_rate=16000, verse_listen_step_sec=8,
        verse_listen_max_sec=60, verse_score_threshold=0.55,
    )
    monkeypatch.setattr(verse_service, "get_settings", lambda: settings)
    monkeypatch.setattr(
        verse_service, "decode_upload_bytes",
        lambda *a, **kw: (torch.zeros(1, seconds * 16000), 16000),
    )
    calls = []
    remaining = iter(texts)

    def transcribe(waveform):
        calls.append(waveform.shape[1])
        return next(remaining), []

    # Load the real corpus before replacing settings.
    monkeypatch.setattr(verse_service, "transcribe_waveform", transcribe)
    return calls


def test_more_audio_resolves_repeated_refrain(monkeypatch):
    verse_service.get_index()
    calls = setup_audio(monkeypatch, [
        "فباي الاء ربكما تكذبان",
        "خلق الانسان من صلصال كالفخار",
    ])
    result = verse_service.identify_progressive_bytes(b"audio", 1)
    top = result["matches"][0]
    assert (top["surah"], top["ayah_start"], top["ayah_end"]) == (55, 13, 14)
    assert result["confident"]
    assert not result["needs_more_audio"]
    assert result["audio_seconds"] == 16
    assert len(calls) == 2  # Do not transcribe unused later audio.


def test_uncertain_audio_requests_more(monkeypatch):
    verse_service.get_index()
    setup_audio(monkeypatch, ["فباي الاء ربكما تكذبان"], seconds=8)
    result = verse_service.identify_progressive_bytes(b"audio", 1)
    assert not result["confident"]
    assert result["needs_more_audio"]
    assert not result["listen_limit_reached"]


def test_listening_stops_at_duration_limit(monkeypatch):
    verse_service.get_index()
    calls = setup_audio(monkeypatch, ["فباي الاء ربكما تكذبان"] * 8, seconds=80)
    result = verse_service.identify_progressive_bytes(b"audio", 3)
    assert not result["confident"]
    assert not result["needs_more_audio"]
    assert result["listen_limit_reached"]
    assert result["audio_seconds"] == 60
    assert len(calls) == 8
    assert max(calls) == 8 * 16000


@pytest.mark.parametrize("ayah", [16, 30, 59, 77])
def test_distinct_rahman_occurrences_resolve_with_context(monkeypatch, ayah):
    index = verse_service.get_index()
    refrain = index._by_key[(55, ayah)].text
    following = index._by_key[(55, ayah + 1)].text
    assert index._by_key[(55, ayah)].normalized == index._by_key[(55, 13)].normalized
    setup_audio(monkeypatch, [refrain, following], seconds=16)
    result = verse_service.identify_progressive_bytes(b"audio", 1)
    top = result["matches"][0]
    assert (top["surah"], top["ayah_start"], top["ayah_end"]) == (55, ayah, ayah + 1)
    assert result["confident"]


def test_all_rahman_refrain_positions_remain_ambiguous():
    index = verse_service.get_index()
    refrain = index._by_key[(55, 13)].normalized
    occurrences = [v for v in index.verses if v.surah == 55 and v.normalized == refrain]
    assert len(occurrences) == 31
    for verse in occurrences:
        matches = verse_service.identify_transcript(verse.text, 10)
        assert not verse_service.is_confident(matches)
        assert len(matches) == 10
