"""Eviction must preserve active inference and release idle native sessions."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from app.core import asr, embeddings, inference
from app.core.config import get_settings


@pytest.fixture
def low_memory(monkeypatch):
    monkeypatch.setattr(get_settings(), "low_memory", True)
    monkeypatch.setattr(inference, "release_unused_memory", lambda: None)


def test_switching_evicts_only_inactive_model(low_memory, monkeypatch):
    reciter = object()
    verse = object()
    monkeypatch.setattr(embeddings, "_classifier", reciter)
    monkeypatch.setattr(asr, "_model", verse)
    with inference.model_execution("reciter"):
        assert embeddings._classifier is reciter
        assert asr._model is None
    assert embeddings._classifier is None
    with inference.model_execution("verse"):
        assert embeddings._classifier is None


def test_switch_waits_for_active_inference(low_memory, monkeypatch):
    reciter = object()
    monkeypatch.setattr(embeddings, "_classifier", reciter)
    active = Event()
    release = Event()
    attempting_switch = Event()

    def recognize():
        with inference.model_execution("reciter"):
            active.set()
            assert release.wait(5)
            assert embeddings._classifier is reciter

    def switch():
        assert active.wait(5)
        attempting_switch.set()
        with inference.model_execution("verse"):
            assert embeddings._classifier is None

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(recognize)
        second = pool.submit(switch)
        try:
            assert attempting_switch.wait(5)
            assert embeddings._classifier is reciter
        finally:
            release.set()
        first.result(timeout=5)
        second.result(timeout=5)


def test_failure_releases_execution_slot_and_trims(low_memory, monkeypatch):
    trims = []
    monkeypatch.setattr(inference, "release_unused_memory", lambda: trims.append(1))
    with pytest.raises(ValueError, match="test failure"):
        with inference.model_execution("verse"):
            raise ValueError("test failure")
    assert len(trims) == 2
    assert inference.inference_slot.acquire(timeout=1)
    inference.inference_slot.release()


def test_disabled_profile_preserves_cached_models(monkeypatch):
    monkeypatch.setattr(get_settings(), "low_memory", False)
    reciter, verse = object(), object()
    monkeypatch.setattr(embeddings, "_classifier", reciter)
    monkeypatch.setattr(asr, "_model", verse)
    trims = []
    monkeypatch.setattr(inference, "release_unused_memory", lambda: trims.append(1))
    with inference.model_execution("reciter"):
        pass
    with inference.model_execution("verse"):
        pass
    assert embeddings._classifier is reciter
    assert asr._model is verse
    assert trims == []
