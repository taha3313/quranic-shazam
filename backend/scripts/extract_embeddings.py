"""Compute mean speaker embeddings per reciter and save them to .npy.

Usage:
    uv run python -m scripts.extract_embeddings --dataset-dir data/recitations_clips
    make embeddings
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
from tqdm import tqdm

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build reciter embedding profiles.")
    p.add_argument("--dataset-dir", default="data/recitations_clips")
    p.add_argument("--output", default="data/reciters_embeddings.npy")
    p.add_argument("--limit-per-reciter", type=int, default=80,
                   help="Max clips per reciter (0 = all). 80 x 10s is plenty for a stable mean.")
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = build_parser().parse_args(argv)

    # Import lazily so --help works without torch/speechbrain installed.
    from app.core.embeddings import embedding_from_file

    dataset_dir = Path(args.dataset_dir)
    output = Path(args.output)
    if not dataset_dir.exists():
        logger.error("Dataset dir %s does not exist. Run: make data", dataset_dir)
        return 1

    db: dict[str, np.ndarray] = {}
    for reciter_dir in sorted(d for d in dataset_dir.iterdir() if d.is_dir()):
        files = sorted(f for f in reciter_dir.iterdir() if f.is_file())
        if args.limit_per_reciter:
            # Round-robin across surahs so the mean reflects the whole
            # training pool, not just the first (longest) surah's clips.
            per_surah: dict[str, list[Path]] = {}
            for f in files:
                per_surah.setdefault(f.stem.split("_")[0], []).append(f)
            picked: list[Path] = []
            pools = list(per_surah.values())
            while len(picked) < args.limit_per_reciter and pools:
                for pool in list(pools):
                    picked.append(pool.pop(0))
                    if len(picked) >= args.limit_per_reciter:
                        break
                pools = [p for p in pools if p]
            files = picked
        logger.info("Processing %s (%d files) ...", reciter_dir.name, len(files))
        embs: list[np.ndarray] = []
        for path in tqdm(files, desc=reciter_dir.name):
            try:
                embs.append(embedding_from_file(path))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Skipped %s: %s", path.name, exc)
        if embs:
            db[reciter_dir.name] = np.mean(np.stack(embs), axis=0)
            logger.info("%s: averaged %d embeddings", reciter_dir.name, len(embs))

    output.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(output), db)
    logger.info("Saved %d reciter profiles to %s", len(db), output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
