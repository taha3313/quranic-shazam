"""Application settings loaded from environment with sane defaults."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QD_", env_file=".env", extra="ignore")

    # Paths (relative to backend/ unless absolute)
    data_dir: Path = BACKEND_ROOT / "data"
    embeddings_path: Path = BACKEND_ROOT / "data" / "reciters_embeddings.npy"
    sample_rate: int = 16000

    # Model
    embedding_model_source: str = "speechbrain/spkrec-ecapa-voxceleb"
    embedding_dim_fallback: int = 192
    # Load the embedding model during startup instead of on first request.
    warm_model: bool = False

    # API
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080"
    max_upload_mb: int = 25
    # Identify only the first N seconds of an upload; longer audio is a
    # CPU DoS vector and adds no accuracy beyond this.
    max_audio_sec: int = 30
    top_k_default: int = 3

    # Live recognition
    live_window_sec: float = 5.0
    live_max_duration_sec: float = 30.0
    live_confidence_threshold: float = 0.85

    # Verse identification (ASR + matching; separate from the reciter pipeline)
    verse_corpus_path: Path = BACKEND_ROOT / "data" / "quran_verses.json"
    asr_model_source: str = "OdyAsh/faster-whisper-base-ar-quran"
    asr_device: str = "cpu"
    asr_compute_type: str = "int8"
    # Fine-tuned Whisper accuracy degrades badly past ~30 s (documented on
    # the model cards); cap tighter here since ranges need clean word counts.
    verse_max_audio_sec: int = 20
    verse_listen_step_sec: int = 20
    verse_listen_max_sec: int = 60
    # Below this top-1 score the endpoint reports no confident match.
    verse_score_threshold: float = 0.55

    # Dataset pipeline
    cdn_base_url: str = "https://cdn.islamic.network/quran/audio/128"
    clip_duration_ms: int = 10_000
    clip_overlap_ms: int = 5_000

    @property
    def allowed_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
