"""Serialize model execution so simultaneous requests do not multiply peak RAM."""

from threading import Semaphore

inference_slot = Semaphore(1)
