"""Concurrency regression test: inference must not block the event loop.

Detects event-loop starvation with a heartbeat: a ticker task increments a
counter every 5 ms while the identify request runs a 1.5 s *blocking* sleep
(stand-in for ECAPA + decode). If the route executes that work directly on
the loop, the ticker stalls and the test fails (audit finding C1).

Note: a naive "time the health request" check is fooled here — the loop
block also delays the test's own ``asyncio.sleep`` scheduling, so the
measurement window silently shifts past the block.
"""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from app.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _wav_bytes(seconds: float = 1.0) -> bytes:
    import io

    import numpy as np
    import soundfile as sf

    buf = io.BytesIO()
    sf.write(buf, np.zeros(int(16000 * seconds), dtype="float32"), 16000, format="wav")
    return buf.getvalue()


async def test_event_loop_free_during_identification(
    fake_env, wav_bytes, monkeypatch, anyio_backend
):
    import app.services.reciter_service as svc

    def blocking_identify(data, top_k):
        time.sleep(1.5)  # stand-in for a heavy ECAPA forward pass
        return [{"reciter": "alpha", "display": "Alpha", "score": 0.9}]

    monkeypatch.setattr(svc, "identify_upload_bytes", blocking_identify)

    ticks = 0

    async def heartbeat():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.005)
            ticks += 1

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        beat = asyncio.create_task(heartbeat())
        identify = asyncio.create_task(
            ac.post(
                "/identify_reciter",
                files={"file": ("clip.wav", wav_bytes, "audio/wav")},
            )
        )
        resp = await identify
        beat.cancel()
        try:
            await beat
        except asyncio.CancelledError:
            pass

    assert resp.status_code == 200
    # 1.5 s of identify time: a free loop yields ~300 ticks at 5 ms; a
    # blocked loop yields only the ticks that ran before identify started.
    assert ticks > 150, (
        f"heartbeat got only {ticks} ticks during a 1.5 s inference — "
        "event loop is blocked (C1 regression)"
    )
