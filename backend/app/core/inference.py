"""Serialize model execution and evict the inactive model in low-memory mode."""

from contextlib import contextmanager
from threading import Semaphore
from typing import Literal

from app.core.config import get_settings
from app.core.memory import release_unused_memory

inference_slot = Semaphore(1)


@contextmanager
def model_execution(kind: Literal["reciter", "verse"]):
    # Hold this slot through generator consumption and cleanup, so another
    # request cannot release a model that is still executing.
    with inference_slot:
        low_memory = get_settings().low_memory
        if low_memory:
            if kind == "reciter":
                from app.core.asr import release_model
            else:
                from app.core.embeddings import release_model
            release_model()
            release_unused_memory()
        try:
            yield
        finally:
            if low_memory:
                # Session caches can grow across variable input shapes. Drop the
                # active model too, so each request has a fresh bounded lifecycle.
                if kind == "reciter":
                    from app.core.embeddings import release_model
                else:
                    from app.core.asr import release_model
                release_model()
                release_unused_memory()
