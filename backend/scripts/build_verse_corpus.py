"""Build backend/data/quran_verses.json — the vendored verse corpus.

Source: alquran.cloud ``quran-simple-clean`` edition — the Tanzil "Simple
(Clean)" Imla'i text, unvocalized. We deliberately do NOT use the Uthmani
edition: ASR output (tarteel/whisper-base-ar-quran et al.) is standard
Imla'i orthography, so matching against Imla'i avoids orthography
mismatches (dagger alef, alef wasla, small letters) across the whole Quran.

Quirks handled:
- BOM at the start of the payload,
- the basmala is prepended to ayah 1 of every surah except Al-Fatiha
  (stripped, except surah 1 where it *is* ayah 1; 27:30 keeps its
  mid-verse basmala),
- surah names arrive prefixed with "سورة" (sometimes diacritized) —
  stripped via the shared normalizer,

Run: uv run python scripts/build_verse_corpus.py
"""

from __future__ import annotations

import json
import logging
import sys
import urllib.request
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.arabic_norm import normalize_arabic  # noqa: E402

logger = logging.getLogger(__name__)

QURAN_URL = "https://api.alquran.cloud/v1/quran/quran-simple-clean"
BASMALA = "بسم الله الرحمن الرحيم"
OUT_PATH = BACKEND_ROOT / "data" / "quran_verses.json"


def fetch_json(url: str):
    with urllib.request.urlopen(url, timeout=120) as resp:  # noqa: S310 - fixed host
        return json.loads(resp.read().decode("utf-8"))


def _clean_surah_name(raw: str) -> str:
    """'سُورَةُ الإِخۡلَاصِ' → 'الاخلاص' (unvocalized, no prefix)."""
    name = normalize_arabic(raw).split()
    if name and name[0] in ("سورة", "سوره"):
        name = name[1:]
    return " ".join(name)


def verse_text(surah: int, ayah_no: int, raw: str) -> str:
    text = raw.replace("\ufeff", "").strip()
    if ayah_no == 1 and surah != 1 and text.startswith(BASMALA):
        text = text[len(BASMALA):].strip()
    return text


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    payload = fetch_json(QURAN_URL)
    if payload.get("status") != "OK":
        raise SystemExit(f"Unexpected API status: {payload.get('status')}")
    surahs = payload["data"]["surahs"]
    if len(surahs) != 114:
        raise SystemExit(f"Expected 114 surahs, got {len(surahs)}")

    surah_names: dict[int, str] = {}
    surah_translit: dict[int, str] = {}
    verses: list[dict] = []
    for surah in surahs:
        s_no = surah["number"]
        surah_names[s_no] = _clean_surah_name(surah["name"])
        surah_translit[s_no] = surah.get("englishName", "")
        for ayah in surah["ayahs"]:
            text = verse_text(s_no, ayah["numberInSurah"], ayah["text"])
            if not text:
                raise SystemExit(f"Empty text for {s_no}:{ayah['numberInSurah']}")
            verses.append(
                {
                    "surah": s_no,
                    "ayah": ayah["numberInSurah"],
                    "text": text,  # verbatim source text (Imla'i)
                    "normalized": normalize_arabic(text),
                }
            )

    if len(verses) != 6236:
        raise SystemExit(f"Expected 6236 verses, got {len(verses)}")

    out = {
        "source": "https://api.alquran.cloud/v1/quran/quran-simple-clean (Tanzil text)",
        "license": (
            "Quran text: Tanzil.net — verbatim redistribution, attribution "
            "required (https://tanzil.net)"
        ),
        "surah_names": surah_names,
        "surah_transliterations": surah_translit,
        "verses": verses,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote %d verses to %s", len(verses), OUT_PATH)


if __name__ == "__main__":
    main()
