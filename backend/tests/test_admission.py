"""Admission controls active work while allowing health and completed clients."""

import asyncio

import httpx
import pytest
from starlette.responses import JSONResponse

from app.core.admission import LowMemoryAdmissionMiddleware
from app.core.config import get_settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_excess_recognition_is_rejected_before_body_parsing(monkeypatch):
    monkeypatch.setattr(get_settings(), "low_memory", True)
    release = asyncio.Event()
    both_started = asyncio.Event()
    started = 0

    async def inner(scope, receive, send):
        nonlocal started
        if scope["path"] != "/health":
            started += 1
            if started == 2:
                both_started.set()
            await release.wait()
        await JSONResponse({"ok": True})(scope, receive, send)

    middleware = LowMemoryAdmissionMiddleware(inner)
    transport = httpx.ASGITransport(app=middleware)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        pending = [asyncio.create_task(client.post("/identify_reciter")) for _ in range(2)]
        try:
            await asyncio.wait_for(both_started.wait(), timeout=5)
            response = await client.post("/identify_verse", content=b"not parsed")
            assert response.status_code == 503
            assert response.headers["Retry-After"] == "1"
            assert started == 2
            assert (await client.get("/health")).status_code == 200
        finally:
            release.set()
            results = await asyncio.gather(*pending)
        assert all(result.status_code == 200 for result in results)
        # Closed work frees admission even if clients keep their connections alive.
        assert (await client.post("/identify_reciter")).status_code == 200
