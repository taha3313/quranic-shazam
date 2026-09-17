"""Response schemas for the reciter API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReciterMatch(BaseModel):
    reciter: str
    display: str | None = None
    score: float = Field(ge=-1.0, le=1.0)


class IdentifyResponse(BaseModel):
    matches: list[ReciterMatch]


class VerseMatch(BaseModel):
    surah: int
    surah_name: str | None = None
    ayah_start: int
    ayah_end: int
    score: float
    words_matched: int
    words_total: int
    text: str | None = None


class IdentifyVerseResponse(BaseModel):
    transcript: str | None = None
    confident: bool
    matches: list[VerseMatch]
    needs_more_audio: bool = False
    listen_limit_reached: bool = False
    audio_seconds: float | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    reciters_loaded: int
    model_loaded: bool
