"""FastAPI application factory."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.live_reciter import router as live_router
from app.api.routes.reciter import router as reciter_router
from app.api.schemas import HealthResponse
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    logger.info("Data dir: %s", settings.data_dir)
    # Warm the embeddings DB (not the heavy model) so misconfig fails fast.
    from app.services import reciter_service

    db = reciter_service.get_database()
    logger.info("Reciters in DB at startup: %d", len(db))
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Quranic Shazam - Reciter Identifier", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    health_router = APIRouter(tags=["health"])

    @health_router.get("/health", response_model=HealthResponse)
    def health():
        from app.core import embeddings as emb_module
        from app.services import reciter_service

        db = reciter_service.get_database()
        return HealthResponse(
            reciters_loaded=len(db),
            model_loaded=emb_module._classifier is not None,
        )

    app.include_router(health_router)
    app.include_router(reciter_router)
    app.include_router(live_router)
    return app


app = create_app()
