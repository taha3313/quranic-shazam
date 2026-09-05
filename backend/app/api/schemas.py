"""Response schemas for the reciter API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReciterMatch(BaseModel):
    reciter: str
    display: str | None = None
    score: float = Field(ge=-1.0, le=1.0)


class IdentifyResponse(BaseModel):
    matches: list[ReciterMatch]


class HealthResponse(BaseModel):
    status: str = "ok"
    reciters_loaded: int
    model_loaded: bool
