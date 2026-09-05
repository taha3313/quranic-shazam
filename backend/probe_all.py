"""Verify train/eval availability for all 20 reciters via unified helpers."""

import logging
import sys

sys.path.insert(0, ".")

from scripts.sources import EVAL_SURAHS, RECITERS, TRAIN_SURAHS, qa_exists, surahquran_exists

logging.basicConfig(level=logging.WARNING)

for key, spec in RECITERS.items():
    if spec.qa_id is not None:
        t = [s for s in TRAIN_SURAHS if qa_exists(key, s)]
        e = [s for s in EVAL_SURAHS if qa_exists(key, s)]
        print(f"{key} [qa]: train={len(t)}/8 eval={len(e)}/4")
    elif spec.sq_slug is not None:
        t = [s for s in TRAIN_SURAHS if surahquran_exists(key, s)]
        e = [s for s in EVAL_SURAHS if surahquran_exists(key, s)]
        print(f"{key} [sq]: train={len(t)}/8 eval={len(e)}/4")
    else:
        print(f"{key}: NO SOURCE")
