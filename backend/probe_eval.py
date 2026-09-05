"""Check short-surah availability for the eval pool (all 20 reciters)."""

import sys

sys.path.insert(0, ".")

from scripts.sources import RECITERS, qa_exists, reciter_origin, surahquran_exists

CANDIDATES = [78, 87, 93, 112]

for key in RECITERS:
    origin = reciter_origin(key)
    exists = qa_exists if origin == "quranicaudio" else surahquran_exists
    ok = [s for s in CANDIDATES if exists(key, s)]
    print(f"{key} [{origin}]: {ok}")
