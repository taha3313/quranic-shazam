"""Bound decoded HTTP uploads independently of idle keep-alive connections."""

from threading import BoundedSemaphore

from starlette.responses import JSONResponse

from app.core.config import get_settings

_RECOGNITION_PATHS = {
    "/identify_reciter",
    "/identify_verse",
    "/identify_verse_progressive",
}


class LowMemoryAdmissionMiddleware:
    def __init__(self, app, capacity: int = 2):
        self.app = app
        self.slots = BoundedSemaphore(capacity)

    async def __call__(self, scope, receive, send):
        limited = (
            scope["type"] == "http"
            and scope["path"] in _RECOGNITION_PATHS
            and get_settings().low_memory
        )
        if not limited:
            await self.app(scope, receive, send)
            return
        if not self.slots.acquire(blocking=False):
            response = JSONResponse(
                {"detail": "Recognition is busy. Please retry shortly."},
                status_code=503,
                headers={"Retry-After": "1"},
            )
            await response(scope, receive, send)
            return
        try:
            # Acquire before multipart parsing, and hold through response delivery.
            await self.app(scope, receive, send)
        finally:
            self.slots.release()
