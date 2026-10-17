"""Reproducible conversion parity and fresh-process resource benchmark.

Run from backend/ with export dependencies. Uses existing dataset clips, NOT a
held-out accuracy set. The report records every clip, vector, score and duration.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

import numpy as np


def worker(mode, manifest, output):
    from app.core.audio import load_audio_file
    from app.core.similarity import rank_reciters
    from app.services.reciter_service import get_database

    if mode == "torch":
        import torch

        torch.set_num_threads(2)
        from scripts.torch_reference import embedding_from_waveform
    else:
        from app.core.embeddings import embedding_from_waveform
    database = get_database()
    rows = []
    cold = None
    for sample in json.loads(Path(manifest).read_text()):
        if mode == "torch":
            import soundfile as sf
            import torchaudio

            raw, original_sr = sf.read(sample["path"], dtype="float32", always_2d=True)
            original = torch.from_numpy(raw.T).mean(dim=0, keepdim=True)
            waveform = torchaudio.functional.resample(original, original_sr, 16000).numpy()
            sr = 16000
        else:
            waveform, sr = load_audio_file(sample["path"])
        # Repeat real audio when probing a longer input shape, identically in both modes.
        count = int(sample["seconds"] * sr)
        waveform = np.tile(waveform, (1, (count + waveform.shape[1] - 1) // waveform.shape[1]))
        waveform = waveform[:, :count]
        started = time.perf_counter()
        vector = embedding_from_waveform(waveform, sr)
        elapsed = time.perf_counter() - started
        if cold is None:
            cold = elapsed
        rows.append(
            {
                **sample,
                "seconds_elapsed": elapsed,
                "vector": vector.tolist(),
                "matches": rank_reciters(vector, database, top_k=len(database)),
            }
        )
    Path(output).write_text(
        json.dumps(
            {
                "mode": mode,
                "rows": rows,
                "cold_seconds": cold,
                "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                "forbidden_imports": [
                    n for n in ("torch", "torchaudio", "speechbrain") if n in sys.modules
                ],
            },
            indent=2,
        )
        + "\n"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", choices=["torch", "onnx"])
    parser.add_argument("--manifest")
    parser.add_argument("--output", default="data/eval_reports/onnx-parity")
    parser.add_argument("--runtime-python", default=sys.executable)
    args = parser.parse_args()
    if args.worker:
        worker(args.worker, args.manifest, args.output)
        return
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    samples = []
    for directory in sorted(Path("data/recitations_clips").iterdir()):
        if not directory.is_dir():
            continue
        paths = sorted(directory.glob("*.wav"))
        for index, seconds in enumerate((1, 5, 10)):
            samples.append({"path": str(paths[index]), "seconds": seconds})
    for directory in sorted(Path("data/recitations_clips").iterdir())[:3]:
        samples.append({"path": str(sorted(directory.glob("*.wav"))[0]), "seconds": 30})
    manifest = out / "manifest.json"
    manifest.write_text(json.dumps(samples, indent=2) + "\n")
    for mode, python in (("torch", sys.executable), ("onnx", args.runtime_python)):
        subprocess.run(
            [
                python,
                "-m",
                "scripts.benchmark_reciter_onnx",
                "--worker",
                mode,
                "--manifest",
                str(manifest),
                "--output",
                str(out / f"{mode}.json"),
            ],
            check=True,
            env={**os.environ, "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"},
        )
    baseline = json.loads((out / "torch.json").read_text())
    candidate = json.loads((out / "onnx.json").read_text())
    comparisons = []
    for a, b in zip(baseline["rows"], candidate["rows"], strict=True):
        va, vb = np.asarray(a["vector"]), np.asarray(b["vector"])
        scores_a = {m["reciter"]: m["score"] for m in a["matches"]}
        scores_b = {m["reciter"]: m["score"] for m in b["matches"]}
        comparisons.append(
            {
                "path": a["path"],
                "seconds": a["seconds"],
                "cosine": float(va @ vb / np.linalg.norm(va) / np.linalg.norm(vb)),
                "max_score_difference": max(abs(scores_a[k] - scores_b[k]) for k in scores_a),
                "top1_equal": a["matches"][0]["reciter"] == b["matches"][0]["reciter"],
                "top3_equal": [m["reciter"] for m in a["matches"][:3]]
                == [m["reciter"] for m in b["matches"][:3]],
                "confidence_equal": (a["matches"][0]["score"] >= 0.85)
                == (b["matches"][0]["score"] >= 0.85),
            }
        )
    summary = {
        "samples": len(comparisons),
        "provenance": "local dataset conversion parity only",
        "minimum_cosine": min(c["cosine"] for c in comparisons),
        "max_score_difference": max(c["max_score_difference"] for c in comparisons),
        "top1_equal": sum(c["top1_equal"] for c in comparisons),
        "top3_equal": sum(c["top3_equal"] for c in comparisons),
        "confidence_equal": sum(c["confidence_equal"] for c in comparisons),
        "resources": {
            m: {
                "peak_rss_mib": data["peak_rss_mib"],
                "warm_median_seconds": float(
                    np.median([r["seconds_elapsed"] for r in data["rows"][1:]])
                ),
                "cold_seconds": data["cold_seconds"],
                "forbidden_imports": data["forbidden_imports"],
            }
            for m, data in (("torch", baseline), ("onnx", candidate))
        },
        "comparisons": comparisons,
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "comparisons"}, indent=2))
    if not all(
        c["top1_equal"]
        and c["top3_equal"]
        and c["confidence_equal"]
        and c["cosine"] > 0.9999
        and c["max_score_difference"] < 1e-4
        for c in comparisons
    ):
        raise SystemExit("Conversion parity gate failed; inspect summary.json")


if __name__ == "__main__":
    main()
