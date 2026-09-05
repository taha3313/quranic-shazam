"""Deep evaluation harness: confusion matrix, precision/recall, top-k,
score distributions, similarity margins, per-surah and per-duration
breakdowns. Emits machine-readable JSON + a human-readable Markdown report.

The identification logic (profiles + cosine ranking) is untouched; this
script only measures it. The 97.31% top-1 baseline from scripts/evaluate.py
must reproduce here under the same defaults.

Usage:
    uv run python -m scripts.evaluate_report
    uv run python -m scripts.evaluate_report --durations 5 10
    uv run python -m scripts.evaluate_report --reciters abkar dosari
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import tempfile
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from scripts.evaluate import fetch_audio
from scripts.generate_data import split_into_clips
from scripts.sources import EVAL_SURAHS, RECITERS

logger = logging.getLogger(__name__)

DURATIONS_SEC = (10.0, 5.0)  # evaluated longest-first; 10 s == baseline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Deep evaluation report.")
    p.add_argument("--reciters", nargs="*", default=list(RECITERS))
    p.add_argument("--surahs", nargs="*", type=int, default=None)
    p.add_argument("--clip-ms", type=int, default=10_000)
    p.add_argument("--overlap-ms", type=int, default=5_000)
    p.add_argument("--max-clips-per-surah", type=int, default=12)
    p.add_argument("--durations", nargs="*", type=float, default=list(DURATIONS_SEC),
                   help="Clip lengths (s) to evaluate; longest is the baseline.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out-dir", default="data/eval_reports")
    return p


# ---------------- evaluation loop ----------------

def collect_records(args) -> list[dict]:
    """Run every eval clip through the service; keep per-clip results."""
    from app.services import reciter_service

    db = reciter_service.get_database()
    if not db:
        raise SystemExit("No embeddings loaded. Run: make embeddings")

    durations = sorted({d for d in args.durations}, reverse=True)
    surahs = args.surahs or EVAL_SURAHS
    records: list[dict] = []

    for reciter in args.reciters:
        if reciter not in RECITERS:
            logger.warning("Unknown reciter %s, skipping.", reciter)
            continue
        with tempfile.TemporaryDirectory(prefix=f"qd-rep-{reciter}-") as tmp:
            tmpdir = Path(tmp)
            for surah in surahs:
                try:
                    audio = fetch_audio("auto", reciter, surah)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("download failed %s %s: %s", reciter, surah, exc)
                    continue
                clips = split_into_clips(audio, args.clip_ms, args.overlap_ms)
                for idx, clip in enumerate(clips[: args.max_clips_per_surah], 1):
                    path = tmpdir / f"{surah}_{idx}.wav"
                    clip.export(str(path), format="wav")
                    for dur in durations:
                        start = time.monotonic()
                        try:
                            query = _trimmed_waveform(path, dur)
                            matches = reciter_service.identify_waveform(
                                query, 16000, top_k=min(5, len(db)),
                            )
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("embed failed %s: %s", path.name, exc)
                            continue
                        records.append({
                            "reciter": reciter,
                            "surah": surah,
                            "clip": idx,
                            "duration_sec": dur,
                            "matches": matches,
                            "latency_ms": round((time.monotonic() - start) * 1000, 1),
                        })
                logger.info("%s surah %s done (%d clips)", reciter, surah,
                            min(len(clips), args.max_clips_per_surah))
    return records


def _trimmed_waveform(path: Path, dur_sec: float):
    """Load the clip file and keep only its first `dur_sec` seconds."""
    from app.core.audio import load_audio_file

    waveform, sr = load_audio_file(path)
    max_samples = int(dur_sec * sr)
    if waveform.shape[1] > max_samples:
        waveform = waveform[:, :max_samples]
    return waveform


# ---------------- aggregation ----------------

def aggregate(records: list[dict]) -> dict:
    baseline_dur = max(r["duration_sec"] for r in records)
    base = [r for r in records if r["duration_sec"] == baseline_dur]

    def top1_correct(r):
        return bool(r["matches"]) and r["matches"][0]["reciter"] == r["reciter"]

    def in_topk(r, k):
        return any(m["reciter"] == r["reciter"] for m in r["matches"][:k])

    keys = sorted({r["reciter"] for r in base})
    confusion = {a: {b: 0 for b in keys} for a in keys}
    for r in base:
        pred = r["matches"][0]["reciter"] if r["matches"] else "<none>"
        confusion.setdefault(pred, {b: 0 for b in keys})
        confusion[r["reciter"]].setdefault(pred, 0)
        confusion[r["reciter"]][pred] += 1

    per_reciter = {}
    for key in keys:
        rows = [r for r in base if r["reciter"] == key]
        n = len(rows)
        correct = sum(top1_correct(r) for r in rows)
        # precision: of all clips *predicted* as key, fraction truly key
        as_pred = [r for r in base if r["matches"] and r["matches"][0]["reciter"] == key]
        precision = (sum(r["reciter"] == key for r in as_pred) / len(as_pred)
                     if as_pred else 0.0)
        confused_with = Counter(
            r["matches"][0]["reciter"] for r in rows
            if r["matches"] and not top1_correct(r)
        )
        per_reciter[key] = {
            "n": n,
            "top1": round(correct / n, 4) if n else 0.0,
            "top3": round(sum(in_topk(r, 3) for r in rows) / n, 4) if n else 0.0,
            "top5": round(sum(in_topk(r, 5) for r in rows) / n, 4) if n else 0.0,
            "precision": round(precision, 4),
            "main_confusion": confused_with.most_common(2),
        }

    correct_scores = [r["matches"][0]["score"] for r in base if top1_correct(r)]
    wrong_scores = [r["matches"][0]["score"] for r in base
                    if r["matches"] and not top1_correct(r)]
    margins = []
    for r in base:
        if len(r["matches"]) >= 2:
            margins.append(r["matches"][0]["score"] - r["matches"][1]["score"])

    by_surah = defaultdict(lambda: [0, 0])
    for r in base:
        by_surah[r["surah"]][1] += 1
        by_surah[r["surah"]][0] += top1_correct(r)

    by_duration = {}
    for dur in sorted({r["duration_sec"] for r in records}, reverse=True):
        rows = [r for r in records if r["duration_sec"] == dur]
        by_duration[f"{dur:g}s"] = {
            "n": len(rows),
            "top1": round(sum(top1_correct(r) for r in rows) / len(rows), 4),
        }

    lat = sorted(r["latency_ms"] for r in base)
    return {
        "baseline_top1": round(sum(top1_correct(r) for r in base) / len(base), 4),
        "top3": round(sum(in_topk(r, 3) for r in base) / len(base), 4),
        "top5": round(sum(in_topk(r, 5) for r in base) / len(base), 4),
        "n_baseline": len(base),
        "per_reciter": per_reciter,
        "confusion_matrix": confusion,
        "score_stats": {
            "correct_mean": round(sum(correct_scores) / len(correct_scores), 4)
            if correct_scores else None,
            "correct_min": round(min(correct_scores), 4) if correct_scores else None,
            "wrong_mean": round(sum(wrong_scores) / len(wrong_scores), 4)
            if wrong_scores else None,
            "wrong_max": round(max(wrong_scores), 4) if wrong_scores else None,
            "margin_mean": round(sum(margins) / len(margins), 4) if margins else None,
            "margin_p10": round(margins[len(margins) // 10], 4) if margins else None,
        },
        "by_surah": {str(s): {"top1": round(c / n, 4), "n": n}
                     for s, (c, n) in sorted(by_surah.items())},
        "by_duration": by_duration,
        "latency_ms_p50": lat[len(lat) // 2] if lat else None,
    }


# ---------------- report rendering ----------------

def render_markdown(agg: dict, args) -> str:
    lines = [
        "# Quranic Shazam — Evaluation Report",
        f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')}_",
        "",
        f"**Baseline top-1: {agg['baseline_top1']*100:.2f}%** "
        f"(n={agg['n_baseline']}) · top-3: {agg['top3']*100:.2f}% · "
        f"top-5: {agg['top5']*100:.2f}% · p50 latency {agg['latency_ms_p50']} ms",
        "",
        "## Per reciter",
        "",
        "| reciter | n | top-1 | top-3 | top-5 | precision | main confusion |",
        "|---|---|---|---|---|---|---|",
    ]
    for key, s in sorted(agg["per_reciter"].items(), key=lambda kv: kv[1]["top1"]):
        conf = ", ".join(f"{k} ({c})" for k, c in s["main_confusion"]) or "—"
        lines.append(
            f"| {key} | {s['n']} | {s['top1']*100:.1f}% | {s['top3']*100:.1f}% "
            f"| {s['top5']*100:.1f}% | {s['precision']*100:.1f}% | {conf} |"
        )
    lines += [
        "",
        "## Score distribution",
        "",
        f"- correct predictions: mean {agg['score_stats']['correct_mean']}, "
        f"min {agg['score_stats']['correct_min']}",
        f"- wrong predictions: mean {agg['score_stats']['wrong_mean']}, "
        f"max {agg['score_stats']['wrong_max']}",
        f"- top1–top2 margin: mean {agg['score_stats']['margin_mean']}, "
        f"p10 {agg['score_stats']['margin_p10']}",
        "",
        "## By surah",
        "",
        "| surah | top-1 | n |", "|---|---|---|",
    ]
    for surah, s in agg["by_surah"].items():
        lines.append(f"| {surah} | {s['top1']*100:.1f}% | {s['n']} |")
    lines += ["", "## By clip duration", "", "| duration | top-1 | n |", "|---|---|---|"]
    for dur, s in agg["by_duration"].items():
        lines.append(f"| {dur} | {s['top1']*100:.1f}% | {s['n']} |")

    lines += ["", "## Confusion matrix (rows=true, cols=predicted, baseline duration)", ""]
    keys = sorted(next(iter(agg["confusion_matrix"].values())))
    short = {k: k[:8] for k in keys}
    lines.append("| true \\ pred | " + " | ".join(short[k] for k in keys) + " |")
    lines.append("|---" * (len(keys) + 1) + "|")
    for true in keys:
        row = agg["confusion_matrix"][true]
        cells = []
        for pred in keys:
            v = row.get(pred, 0)
            cells.append(str(v) if v else "·")
        lines.append(f"| **{short[true]}** | " + " | ".join(cells) + " |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = build_parser().parse_args(argv)
    random.seed(args.seed)

    records = collect_records(args)
    if not records:
        print("No records collected — nothing to report.")
        return 1
    agg = aggregate(records)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = out_dir / f"eval_{stamp}.json"
    md_path = out_dir / f"eval_{stamp}.md"
    json_path.write_text(json.dumps(
        {"generated": stamp, "args": vars(args), "aggregate": agg,
         "records": records},
        indent=1, default=str,
    ))
    md_path.write_text(render_markdown(agg, args))

    print(f"baseline top-1: {agg['baseline_top1']*100:.2f}% "
          f"({agg['n_baseline']} clips) | top-3 {agg['top3']*100:.2f}%")
    print(f"reports written: {json_path} , {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
