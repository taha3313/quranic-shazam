"""Evaluate identification accuracy on fresh (never-trained-on) clips.

Downloads eval-pool surahs per reciter, runs every clip through the service
layer, and reports per-reciter + overall top-1 accuracy.

Usage:
    uv run python -m scripts.evaluate
    uv run python -m scripts.evaluate --reciters maher dosari --surahs 7 23
    make evaluate
"""

from __future__ import annotations

import argparse
import logging
import tempfile
from pathlib import Path

from scripts.generate_data import CDN_BASE_URL, download_surah, split_into_clips
from scripts.sources import EVAL_SURAHS, RECITERS, download_reciter_surah

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Evaluate reciter identification accuracy.")
    p.add_argument("--source",
                   choices=["auto", "quranicaudio", "surahquran", "islamic-cdn"],
                   default="auto")
    p.add_argument("--reciters", nargs="*", default=list(RECITERS))
    p.add_argument("--surahs", nargs="*", type=int, default=None,
                   help="Eval surahs (default: fresh eval pool).")
    p.add_argument("--clip-ms", type=int, default=10_000)
    p.add_argument("--overlap-ms", type=int, default=5_000)
    p.add_argument("--max-clips-per-surah", type=int, default=12,
                   help="Cap eval clips per surah to bound runtime.")
    p.add_argument("--top-k", type=int, default=1)
    return p


def fetch_audio(source: str, reciter: str, surah: int) -> bytes:
    if source == "islamic-cdn":
        spec = RECITERS[reciter]
        assert spec.cdn_code is not None
        return download_surah(CDN_BASE_URL, spec.cdn_code, surah)
    if source == "surahquran":
        from scripts.sources import download_surahquran

        return download_surahquran(reciter, surah)
    if source == "quranicaudio":
        from scripts.sources import download_qa

        return download_qa(reciter, surah)
    return download_reciter_surah(reciter, surah)


def evaluate_reciter(
    source: str, reciter: str, surahs: list[int], args: argparse.Namespace
) -> tuple[int, int]:
    from app.core.embeddings import embedding_from_file
    from app.core.similarity import rank_reciters
    from app.services import reciter_service

    correct, total = 0, 0
    with tempfile.TemporaryDirectory(prefix=f"qd-eval-{reciter}-") as tmp:
        tmpdir = Path(tmp)
        for surah in surahs:
            try:
                audio = fetch_audio(source, reciter, surah)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Download failed %s surah %s: %s", reciter, surah, exc)
                continue
            clips = split_into_clips(audio, args.clip_ms, args.overlap_ms)
            for idx, clip in enumerate(clips[: args.max_clips_per_surah], start=1):
                path = tmpdir / f"{surah}_{idx}.wav"
                clip.export(str(path), format="wav")
                try:
                    query = embedding_from_file(path)
                    matches = rank_reciters(
                        query, reciter_service.get_database(), top_k=args.top_k
                    )
                except FileNotFoundError:
                    logger.error("Embeddings DB missing. Run: make embeddings")
                    raise SystemExit(1) from None
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Skipped %s: %s", path.name, exc)
                    continue
                total += 1
                if matches and matches[0]["reciter"].lower() == reciter.lower():
                    correct += 1
    return correct, total


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = build_parser().parse_args(argv)
    surahs = args.surahs or EVAL_SURAHS

    grand_correct, grand_total = 0, 0
    for reciter in args.reciters:
        if reciter not in RECITERS:
            logger.warning("Unknown reciter %s, skipping.", reciter)
            continue
        correct, total = evaluate_reciter(args.source, reciter, surahs, args)
        acc = (correct / total * 100) if total else 0.0
        logger.info("%s: %.2f%% (%d/%d)", reciter, acc, correct, total)
        print(f"{reciter}: {acc:.2f}% ({correct}/{total})")
        grand_correct += correct
        grand_total += total

    overall = (grand_correct / grand_total * 100) if grand_total else 0.0
    print(f"OVERALL: {overall:.2f}% ({grand_correct}/{grand_total})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
