"""Download Quran recitation clips and split them into overlapping windows.

Sources:
- surahquran (default): mp3 files linked by https://surahquran.com
  (mp3quran.net CDN / archive.org), 12 reciters, curated surah pools.
- islamic-cdn: legacy https://cdn.islamic.network source (3 reciters).

Usage (via make / uv):
    uv run python -m scripts.generate_data --source surahquran
    uv run python -m scripts.generate_data --source surahquran --reciters maher dosari
    make data
"""

from __future__ import annotations

import argparse
import io
import logging
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from pydub import AudioSegment
from tqdm import tqdm

from scripts.sources import (
    RECITERS,
    TRAIN_SURAHS,
    download_reciter_surah,
    download_surahquran,
)

logger = logging.getLogger(__name__)

CDN_BASE_URL = "https://cdn.islamic.network/quran/audio/128"


def surah_exists(base_url: str, reciter_code: str, surah: int, timeout: int = 10) -> bool:
    try:
        resp = requests.head(f"{base_url}/{reciter_code}/{surah}.mp3", timeout=timeout)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def download_surah(base_url: str, reciter_code: str, surah: int, timeout: int = 30) -> bytes:
    resp = requests.get(f"{base_url}/{reciter_code}/{surah}.mp3", stream=True, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def split_into_clips(
    audio_bytes: bytes, clip_ms: int = 10_000, overlap_ms: int = 5_000
) -> list[AudioSegment]:
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes), format="mp3")
    clips: list[AudioSegment] = []
    step = max(clip_ms - overlap_ms, 1)
    start = 0
    while start < len(audio):
        clip = audio[start : start + clip_ms]
        if len(clip) > 1000:
            clips.append(clip)
        start += step
    return clips


def save_clips(clips: list[AudioSegment], out_dir: Path, surah: int) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    for idx, clip in enumerate(clips, start=1):
        clip.export(str(out_dir / f"{surah}_{idx}.wav"), format="wav")
    return len(clips)


def surah_done(dataset_dir: Path, reciter: str, surah: int) -> bool:
    """True if clips were already generated for this surah (resume support)."""
    return (dataset_dir / reciter / f"{surah}_1.wav").exists()


def process_surah_cdn(
    dataset_dir: Path, reciter: str, code: str, surah: int,
    clip_ms: int, overlap_ms: int, force: bool = False,
) -> str:
    if not force and surah_done(dataset_dir, reciter, surah):
        return f"SKIP {reciter} surah {surah}: already downloaded"
    try:
        audio = download_surah(CDN_BASE_URL, code, surah)
        clips = split_into_clips(audio, clip_ms, overlap_ms)
        n = save_clips(clips, dataset_dir / reciter, surah)
        return f"OK {reciter} surah {surah}: {n} clips"
    except Exception as exc:  # noqa: BLE001
        return f"FAIL {reciter} surah {surah}: {exc}"


def process_surah_sq(
    dataset_dir: Path, reciter: str, surah: int, clip_ms: int, overlap_ms: int,
    force: bool = False,
) -> str:
    """Fetch via the reciter's best source (quranicaudio, else surahquran)."""
    if not force and surah_done(dataset_dir, reciter, surah):
        return f"SKIP {reciter} surah {surah}: already downloaded"
    try:
        audio = download_reciter_surah(reciter, surah)
        clips = split_into_clips(audio, clip_ms, overlap_ms)
        n = save_clips(clips, dataset_dir / reciter, surah)
        return f"OK {reciter} surah {surah}: {n} clips"
    except Exception as exc:  # noqa: BLE001
        return f"FAIL {reciter} surah {surah}: {exc}"


def process_surah_surq_only(
    dataset_dir: Path, reciter: str, surah: int, clip_ms: int, overlap_ms: int,
    force: bool = False,
) -> str:
    if not force and surah_done(dataset_dir, reciter, surah):
        return f"SKIP {reciter} surah {surah}: already downloaded"
    try:
        audio = download_surahquran(reciter, surah)
        clips = split_into_clips(audio, clip_ms, overlap_ms)
        n = save_clips(clips, dataset_dir / reciter, surah)
        return f"OK {reciter} surah {surah}: {n} clips"
    except Exception as exc:  # noqa: BLE001
        return f"FAIL {reciter} surah {surah}: {exc}"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Download recitation clips per reciter.")
    p.add_argument("--source",
                   choices=["auto", "quranicaudio", "surahquran", "islamic-cdn"],
                   default="auto",
                   help="auto = quranicaudio, falling back to surahquran per reciter.")
    p.add_argument("--dataset-dir", default="data/recitations_clips")
    p.add_argument("--reciters", nargs="*", default=list(RECITERS),
                   help="Subset of reciter keys to download.")
    p.add_argument("--surahs", nargs="*", type=int, default=None,
                   help="Explicit surah numbers (default: curated pool / random).")
    p.add_argument("--num-surahs", type=int, default=8,
                   help="How many surahs per reciter (islamic-cdn random mode).")
    p.add_argument("--clip-ms", type=int, default=10_000)
    p.add_argument("--overlap-ms", type=int, default=5_000)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--force", action="store_true",
                   help="Re-download even if clips already exist.")
    return p


def run_remote(args: argparse.Namespace, dataset_dir: Path) -> int:
    """Download from quranicaudio/surahquran (auto per reciter unless forced)."""
    from scripts.sources import reciter_origin

    for reciter in args.reciters:
        spec = RECITERS.get(reciter)
        if spec is None:
            logger.warning("Unknown reciter %s, skipping.", reciter)
            continue
        if args.source == "quranicaudio" and spec.qa_id is None:
            logger.warning("No quranicaudio source for %s, skipping.", reciter)
            continue
        if args.source == "surahquran" and spec.sq_slug is None:
            logger.warning("No surahquran source for %s, skipping.", reciter)
            continue
        worker = (process_surah_surq_only if args.source == "surahquran"
                  else process_surah_sq)
        if args.source != "auto":
            logger.info("Downloading %s via %s", reciter, args.source)
        else:
            logger.info("Downloading %s via %s", reciter, reciter_origin(reciter))
        surahs = args.surahs or TRAIN_SURAHS
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [
                pool.submit(worker, dataset_dir, reciter, surah,
                            args.clip_ms, args.overlap_ms, args.force)
                for surah in surahs
            ]
            for fut in tqdm(as_completed(futures), total=len(futures), desc=reciter):
                result = fut.result()
                log = logger.info if result.startswith(("OK", "SKIP")) else logger.warning
                log(result)
    return 0


def run_cdn(args: argparse.Namespace, dataset_dir: Path) -> int:
    for reciter in args.reciters:
        spec = RECITERS.get(reciter)
        if spec is None or spec.cdn_code is None:
            logger.warning("Unknown reciter %s, skipping.", reciter)
            continue
        logger.info("Scanning available surahs for %s ...", reciter)
        pool = args.surahs or [s for s in range(1, 115)
                               if surah_exists(CDN_BASE_URL, spec.cdn_code, s)]
        if not pool:
            logger.warning("No surahs available for %s, skipping.", reciter)
            continue
        chosen = random.sample(pool, min(args.num_surahs, len(pool)))
        with ThreadPoolExecutor(max_workers=args.workers) as pool_exec:
            futures = [
                pool_exec.submit(process_surah_cdn, dataset_dir, reciter, spec.cdn_code,
                                 surah, args.clip_ms, args.overlap_ms, args.force)
                for surah in chosen
            ]
            for fut in tqdm(as_completed(futures), total=len(futures), desc=reciter):
                logger.info(fut.result())
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = build_parser().parse_args(argv)
    random.seed(args.seed)

    dataset_dir = Path(args.dataset_dir)
    dataset_dir.mkdir(parents=True, exist_ok=True)

    if args.source == "islamic-cdn":
        return run_cdn(args, dataset_dir)
    return run_remote(args, dataset_dir)


if __name__ == "__main__":
    raise SystemExit(main())
