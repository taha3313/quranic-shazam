"""Verify numerical parity and hard memory limits against a running container.

Run from backend/ after starting the documented low-memory container. Uses local
real recordings and the previous ONNX parity report; no external model calls.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests
import soundfile as sf

from app.core.audio import load_audio_file


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8003")
    parser.add_argument("--container", default="quran-512-probe")
    parser.add_argument("--output", default="data/eval_reports/memory-512/matrix.json")
    parser.add_argument("--baseline-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {"reciter_probes": [], "api_probes": [], "failures": []}

    def docker(*command):
        return subprocess.check_output(["docker", *command], text=True)

    def save():
        report["peak_memory_bytes"] = int(
            docker("exec", args.container, "cat", "/sys/fs/cgroup/memory.peak")
        )
        report["memory_events"] = docker(
            "exec", args.container, "cat", "/sys/fs/cgroup/memory.events"
        )
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")

    def post(url, route, data, filename):
        started = time.monotonic()
        response = requests.post(url + route, files={"file": (filename, data)}, timeout=300)
        response.raise_for_status()
        return {"response": response.json(), "seconds": time.monotonic() - started}

    state = json.loads(docker("inspect", args.container))[0]
    report["memory_limit_bytes"] = state["HostConfig"]["Memory"]
    report["memory_swap_limit_bytes"] = state["HostConfig"]["MemorySwap"]
    report["cpus"] = state["HostConfig"]["NanoCpus"] / 1e9
    assert report["memory_limit_bytes"] == 512 * 1024**2
    assert report["memory_swap_limit_bytes"] == report["memory_limit_bytes"]
    baseline_path = Path("data/eval_reports/onnx-parity/onnx.json")
    report["baseline_sha256"] = hashlib.sha256(baseline_path.read_bytes()).hexdigest()
    baseline = json.loads(baseline_path.read_text())
    for index, sample in enumerate(baseline["rows"]):
        audio, sr = load_audio_file(sample["path"])
        samples = int(sample["seconds"] * sr)
        audio = np.tile(audio, (1, (samples + audio.shape[1] - 1) // audio.shape[1]))
        buffer = io.BytesIO()
        sf.write(buffer, audio[:, :samples].T, sr, format="WAV", subtype="FLOAT")
        result = post(args.url, "/identify_reciter", buffer.getvalue(), "probe.wav")
        actual = result["response"]
        expected = sample["matches"][:3]
        same_order = [m["reciter"] for m in actual["matches"]] == [m["reciter"] for m in expected]
        delta = max(
            abs(a["score"] - b["score"]) for a, b in zip(actual["matches"], expected, strict=True)
        )
        confidence_equal = actual["confident"] == (expected[0]["score"] >= 0.85)
        row = {
            "path": sample["path"],
            "audio_seconds": sample["seconds"],
            "seconds": result["seconds"],
            "same_top3_order": same_order,
            "max_score_difference": delta,
            "confidence_equal": confidence_equal,
            "matches": actual["matches"],
        }
        report["reciter_probes"].append(row)
        if not same_order or delta > 1e-4 or not confidence_equal:
            report["failures"].append({"reciter_parity": row})
        save()
        if (index + 1) % 10 == 0:
            print(f"reciter probes: {index + 1}/{len(baseline['rows'])}", flush=True)

    verse_route = "/identify_verse_progressive?include_transcript=true"
    # Test the whole 60-second continued-listening path with exactly the same
    # audio bytes through the previous service and the low-memory candidate.
    real, sr = load_audio_file("data/verse_audio_eval/Husary_128kbps/112001.mp3")
    requests_to_compare = []
    for seconds in (20, 60):
        samples = seconds * sr
        repeated = np.tile(real, (1, (samples + real.shape[1] - 1) // real.shape[1]))
        buffer = io.BytesIO()
        sf.write(buffer, repeated[:, :samples].T, sr, format="WAV", subtype="FLOAT")
        requests_to_compare.append(
            (f"verse-{seconds}s", verse_route, buffer.getvalue(), "verse.wav")
        )
    for label, source, route in [
        ("webm-reciter", "data/recitations_clips/ghamdi/55_1.wav", "/identify_reciter"),
        ("webm-verse", "data/verse_audio_eval/Husary_128kbps/112001.mp3", verse_route),
    ]:
        data = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                source,
                "-c:a",
                "libopus",
                "-f",
                "webm",
                "pipe:1",
            ],
            capture_output=True,
            check=True,
            timeout=30,
        ).stdout
        requests_to_compare.append((label, route, data, "recording.webm"))
    for label, route, data, filename in requests_to_compare:
        expected = post(args.baseline_url, route, data, filename)
        candidate = post(args.url, route, data, filename)
        equal = equivalent_response(expected["response"], candidate["response"])
        report["api_probes"].append(
            {
                "label": label,
                "baseline": expected,
                "candidate": candidate,
                "equivalent_response": equal,
            }
        )
        if not equal:
            report["failures"].append({"api_parity": label})
        save()
        print(f"API parity: {label}: {equal}", flush=True)

    # Overlap uploads and decode for the two modes. Model execution must remain
    # serialized, and the inactive model must be evicted before the next starts.
    tasks = [
        (verse_route, requests_to_compare[0][2], "verse.wav"),
        ("/identify_reciter", buffer_audio(), "reciter.wav"),
    ]
    for cycle in range(3):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(post, args.url, *task) for task in tasks]
            results = [future.result() for future in futures]
        report["api_probes"].append({"label": f"overlap-{cycle}", "results": results})
        save()
    state = json.loads(docker("inspect", args.container))[0]
    report["oom_killed"] = state["State"]["OOMKilled"]
    report["running"] = state["State"]["Running"]
    save()
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in ("reciter_probes", "api_probes")}, indent=2
        )
    )
    if report["failures"] or report["oom_killed"] or not report["running"]:
        raise SystemExit("Memory/parity gate failed; inspect report")


def equivalent_response(expected, actual):
    """Keep text, rankings and decisions exact, allowing only tiny score drift."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or expected.keys() != actual.keys():
            return False
        for key in expected:
            if key == "score":
                if abs(expected[key] - actual[key]) > 1e-4:
                    return False
            elif not equivalent_response(expected[key], actual[key]):
                return False
        return True
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(equivalent_response(a, b) for a, b in zip(expected, actual, strict=True))
        )
    return expected == actual


def buffer_audio():
    audio, sr = load_audio_file("data/recitations_clips/ghamdi/55_1.wav")
    audio = np.tile(audio, (1, 4))[:, : 30 * sr]
    buffer = io.BytesIO()
    sf.write(buffer, audio.T, sr, format="WAV", subtype="FLOAT")
    return buffer.getvalue()


if __name__ == "__main__":
    main()
