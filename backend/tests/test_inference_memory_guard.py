"""Concurrent reciter and verse requests must not overlap model activations."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
from time import sleep

import numpy as np

from app.services import reciter_service, verse_service


def test_reciter_and_verse_share_model_execution_slot(fake_env, wav_bytes, monkeypatch):
    guard = Lock()
    active = 0
    peak = 0
    starts = Barrier(2)

    def work():
        nonlocal active, peak
        with guard:
            active += 1
            peak = max(peak, active)
        sleep(0.05)
        with guard:
            active -= 1

    def embed(*args):
        work()
        return np.array([1.0, 0.0, 0.0])

    def transcribe(*args):
        work()
        return "", []

    monkeypatch.setattr(reciter_service, "embedding_from_waveform", embed)
    monkeypatch.setattr(verse_service, "transcribe_waveform", transcribe)
    monkeypatch.setattr(verse_service, "identify_transcript", lambda *args: [])

    def identify(service):
        starts.wait(timeout=5)
        return service.identify_upload_bytes(wav_bytes, 3)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(identify, service) for service in (reciter_service, verse_service)]
        for result in results:
            result.result(timeout=10)
    assert peak == 1
