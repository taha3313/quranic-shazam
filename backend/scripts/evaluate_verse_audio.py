"""Real EveryAyah audio evaluation; labels come from source ayah IDs."""

from __future__ import annotations

import io
import json
import time
from pathlib import Path

import requests
import soundfile as sf
import torch

from app.core.audio import decode_upload_bytes
from app.services.verse_service import identify_upload_bytes

ROOT = Path("data/verse_audio_eval")
ROOT.mkdir(parents=True, exist_ok=True)
RECITERS = ["Alafasy_128kbps", "Husary_128kbps", "Minshawy_Murattal_128kbps"]
VERSES = [(1, 5), (112, 1), (97, 3), (36, 58), (55, 14), (2, 255), (55, 13)]
rows = []


def audio(reciter, surah, ayah):
    name = f"{surah:03d}{ayah:03d}.mp3"
    url = f"https://everyayah.com/data/{reciter}/{name}"
    p = ROOT / reciter / name
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, timeout=40)
        r.raise_for_status()
        p.write_bytes(r.content)
    return p.read_bytes(), url


def wav_bytes(wave):
    out = io.BytesIO()
    sf.write(out, wave.squeeze().numpy(), 16000, format="WAV")
    return out.getvalue()


def run(reciter, kind, data, expected, urls, ambiguous=False):
    started = time.perf_counter()
    transcript, matches = identify_upload_bytes(data, 3)
    elapsed = time.perf_counter() - started
    top = matches[0] if matches else None
    predicted = [top["surah"], top["ayah_start"], top["ayah_end"]] if top else None
    confident = (
        bool(top)
        and top["score"] >= 0.55
        and top["words_matched"] >= 2
        and (len(matches) < 2 or top["score"] - matches[1]["score"] >= 0.05)
    )
    row = dict(
        reciter=reciter,
        kind=kind,
        expected=expected,
        predicted=predicted,
        exact=predicted == expected,
        ambiguous=ambiguous,
        confident=confident,
        seconds=round(elapsed, 2),
        transcript=transcript,
        matches=matches,
        sources=urls,
    )
    rows.append(row)
    (ROOT / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {
                k: row[k]
                for k in [
                    "reciter",
                    "kind",
                    "expected",
                    "predicted",
                    "exact",
                    "confident",
                    "seconds",
                    "transcript",
                ]
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


for reciter in RECITERS:
    for surah, ayah in VERSES:
        data, url = audio(reciter, surah, ayah)
        run(
            reciter, "single", data, [surah, ayah, ayah], [url], ambiguous=(surah, ayah) == (55, 13)
        )
    data, url = audio(reciter, 2, 255)
    wave, _ = decode_upload_bytes(data, target_sr=16000)
    mid = wave.shape[1] // 2
    run(reciter, "partial", wav_bytes(wave[:, mid : mid + 8 * 16000]), [2, 255, 255], [url])
    pieces, urls = [], []
    for ayah in [2, 3, 4]:
        data, url = audio(reciter, 112, ayah)
        wave, _ = decode_upload_bytes(data, target_sr=16000)
        pieces.append(wave)
        urls.append(url)
    combined = torch.cat(pieces, dim=1)
    if combined.shape[1] > 20 * 16000:
        print("SKIP range over upload duration cap", reciter, flush=True)
    else:
        run(reciter, "range", wav_bytes(combined), [112, 2, 4], urls)
unique = [r for r in rows if not r["ambiguous"]]
print(
    "SUMMARY",
    len(unique),
    sum(r["exact"] for r in unique),
    "unique exact;",
    sum(r["confident"] and not r["exact"] for r in unique),
    "confident errors",
    flush=True,
)
