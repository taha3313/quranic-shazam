"""Return unused native allocator pages on low-memory Linux deployments."""

from __future__ import annotations

import ctypes
import gc
from functools import lru_cache


@lru_cache(maxsize=1)
def _malloc_trim():
    try:
        trim = ctypes.CDLL(None).malloc_trim
    except AttributeError:
        return None  # Other platforms still benefit from dropping model references.
    trim.argtypes = [ctypes.c_size_t]
    trim.restype = ctypes.c_int
    return trim


def release_unused_memory() -> None:
    gc.collect()
    trim = _malloc_trim()
    if trim is not None:
        trim(0)
