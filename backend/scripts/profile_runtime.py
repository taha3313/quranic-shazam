"""Profile real API requests in a fresh process without loading export tools."""

from __future__ import annotations

import argparse
import io
import json
import resource
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from app.core.audio import load_audio_file
from app.main import app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/eval_reports/onnx-parity/api-runtime.json")
    args = parser.parse_args()
    rows = []
    with TestClient(app) as client:
        health = client.get("/health").json()
        path = Path("data/recitations_clips/ghamdi/55_1.wav")
        audio, sr = load_audio_file(path)
        longer = np.tile(audio, (1, 4))[:, : 30 * sr]
        output = io.BytesIO()
        sf.write(output, longer.T, sr, format="WAV")
        requests = [
            ("/identify_reciter", path.name, path.read_bytes()),
            ("/identify_reciter", "30-seconds.wav", output.getvalue()),
            (
                "/identify_verse_progressive?include_transcript=true",
                "112001.mp3",
                Path("data/verse_audio_eval/Husary_128kbps/112001.mp3").read_bytes(),
            ),
            (
                "/identify_verse_progressive?include_transcript=true",
                "112002.mp3",
                Path("data/verse_audio_eval/Husary_128kbps/112002.mp3").read_bytes(),
            ),
        ]
        for route, filename, data in requests:
            start = time.perf_counter()
            response = client.post(route, files={"file": (filename, data)})
            response.raise_for_status()
            rows.append(
                {
                    "route": route,
                    "filename": filename,
                    "seconds": time.perf_counter() - start,
                    "response": response.json(),
                    "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                }
            )
    report = {
        "initial_health": health,
        "requests": rows,
        "peak_rss_mib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        "forbidden_imports": [
            n for n in ("torch", "torchaudio", "speechbrain") if n in sys.modules
        ],
    }
    Path(args.output).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report["forbidden_imports"]:
        raise SystemExit("Heavy runtime dependency imported")


if __name__ == "__main__":
    main()
