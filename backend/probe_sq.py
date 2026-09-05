"""Probe: resolve surahquran templates for all reciters and check surah availability."""

import logging
import sys

sys.path.insert(0, ".")

from scripts.sources import EVAL_SURAHS, RECITERS, TRAIN_SURAHS, surahquran_exists

logging.basicConfig(level=logging.WARNING)

for key, spec in RECITERS.items():
    if spec.sq_slug is None:
        print(f"{key}: NO SLUG")
        continue
    try:
        ok_train = [s for s in TRAIN_SURAHS if surahquran_exists(key, s)]
        ok_eval = [s for s in EVAL_SURAHS if surahquran_exists(key, s)]
        print(f"{key} ({spec.sq_slug}): train={ok_train} eval={ok_eval}")
    except Exception as exc:  # noqa: BLE001
        print(f"{key} ({spec.sq_slug}): ERROR {exc}")
