"""Real-audio Rahman ambiguity checks; source IDs are ground truth."""

from __future__ import annotations

import argparse
import io
import json
import time
from pathlib import Path

import requests
import soundfile as sf
import torch

from app.core.audio import decode_upload_bytes
from app.services.verse_service import get_index, identify_progressive_bytes

ROOT = Path("data/verse_audio_eval")
RECITERS = ["Alafasy_128kbps", "Husary_128kbps", "Minshawy_Murattal_128kbps"]
REFRAINS = [16, 30, 59, 77]


def fetch_wave(reciter, ayah):
    name = f"055{ayah:03d}.mp3"
    url = f"https://everyayah.com/data/{reciter}/{name}"
    path = ROOT / reciter / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(url, timeout=40)
        response.raise_for_status()
        path.write_bytes(response.content)
    wave, _ = decode_upload_bytes(path.read_bytes(), target_sr=16000)
    return wave, url


def recognize(wave):
    output = io.BytesIO()
    sf.write(output, wave.squeeze().numpy(), 16000, format="WAV")
    started = time.perf_counter()
    result = identify_progressive_bytes(output.getvalue(), 10)
    return result, round(time.perf_counter() - started, 2)


def main(resume=False):
    index = get_index()
    for ayah in REFRAINS:
        assert index._by_key[(55, ayah)].normalized == index._by_key[(55, 13)].normalized
    results_path = ROOT / "rahman_results.json"
    rows = json.loads(results_path.read_text()) if resume and results_path.exists() else []
    rows = [r for r in rows if r["source_ayah"] in REFRAINS and r["reciter"] in RECITERS]
    completed = {(r["reciter"], r["source_ayah"], r["kind"]) for r in rows}
    results_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    for reciter in RECITERS:
        for ayah in REFRAINS:
            refrain, refrain_url = fetch_wave(reciter, ayah)
            following, following_url = fetch_wave(reciter, ayah + 1)
            for kind, wave, urls in [
                ("refrain_only", refrain, [refrain_url]),
                (
                    "with_next_ayah",
                    torch.cat([refrain, following], dim=1),
                    [refrain_url, following_url],
                ),
            ]:
                if (reciter, ayah, kind) in completed:
                    continue
                result, seconds = recognize(wave)
                top = result["matches"][0] if result["matches"] else None
                predicted = [top["surah"], top["ayah_start"], top["ayah_end"]] if top else None
                passed = (
                    not result["confident"] and result["needs_more_audio"]
                    if kind == "refrain_only"
                    else result["confident"] and predicted == [55, ayah, ayah + 1]
                )
                row = {
                    "reciter": reciter,
                    "source_ayah": ayah,
                    "kind": kind,
                    "expected": "uncertain" if kind == "refrain_only" else [55, ayah, ayah + 1],
                    "predicted": predicted,
                    "passed": passed,
                    "seconds": seconds,
                    "sources": urls,
                    **result,
                }
                rows.append(row)
                (ROOT / "rahman_results.json").write_text(
                    json.dumps(rows, ensure_ascii=False, indent=2)
                )
                print(
                    json.dumps(
                        {
                            k: row[k]
                            for k in [
                                "reciter",
                                "source_ayah",
                                "kind",
                                "expected",
                                "predicted",
                                "passed",
                                "confident",
                                "needs_more_audio",
                                "transcript",
                            ]
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
    print("SUMMARY", sum(r["passed"] for r in rows), "/", len(rows), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", action="store_true", help="Reuse completed cases in this run")
    main(resume=parser.parse_args().resume)
