"""Arabic text normalization for Quran transcript ↔ verse matching.

ASR output and corpus text are collapsed to one canonical form so fuzzy
matching compares content, not orthography: diacritics, pausal marks and
alef/ya/ta-marbuta spelling variants are all folded away.
"""

from __future__ import annotations

import unicodedata

# Characters that normalize to something else entirely.
_CHAR_MAP = {
    "ٱ": "ا",  # alef wasla
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ى": "ي",  # alef maqsura
    "ة": "ه",  # ta marbuta
    "ء": "",  # standalone hamza (ءالاء ↔ الاء, شيء ↔ شي)
    "ـ": "",  # tatweel
}

# Marks stripped wholesale: tashkeel, Quranic annotation signs, small
# letters drawn above/below (U+06D6..U+06DC, U+06DF..U+06E8, superscript
# alef U+0670, ...). Unicode Mn covers all of these in the Tanzil texts.
_MARK_CATEGORIES = {"Mn", "Me"}


def normalize_arabic(text: str) -> str:
    """Collapse Arabic text to bare letters for matching.

    Also NFKC-decomposes (folds presentation forms) and drops any remaining
    non-letter characters, so punctuation and foreign digits vanish.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    out: list[str] = []
    for ch in text:
        if ch in _CHAR_MAP:
            out.append(_CHAR_MAP[ch])
            continue
        if unicodedata.category(ch) in _MARK_CATEGORIES:
            continue
        cat = unicodedata.category(ch)
        if ch.isspace():
            out.append(" ")
        elif cat.startswith("L"):
            out.append(ch)
    # Collapse whitespace runs and trim (digits/punct leave holes).
    return " ".join("".join(out).split())


def normalize_words(text: str) -> list[str]:
    """Normalized, whitespace-split word tokens (drops empties)."""
    return normalize_arabic(text).split()
