"""Verse retrieval + alignment over the normalized Quran corpus.

Pure text layer — no model dependencies — so it can be tested and used
standalone. The corpus (``data/quran_verses.json``) holds the verbatim
Tanzil-derived text plus a pre-normalized form (see arabic_norm).

Matching strategy (see docs/AYAH_ID_RESEARCH.md):
1. Candidate retrieval via an inverted word index (fallback: full scan
   when the transcript has almost no indexable words).
2. Word-sequence scoring with difflib: how much of the transcript the
   verse explains (coverage) tempered by how much of the verse is used
   (precision), which keeps repeated-phrase surahs from flooding top-k.
3. Score ordered consecutive spans before choosing the winning range.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

_MAX_RANGE_VERSES = 16


@dataclass
class Verse:
    surah: int
    ayah: int
    text: str
    normalized: str
    words: list[str] = field(default_factory=list)


@dataclass
class VerseMatch:
    surah: int
    ayah_start: int
    ayah_end: int
    score: float
    words_matched: int
    words_total: int
    # Filled by the service from corpus metadata.
    surah_name: str | None = None
    text: str | None = None

    def as_dict(self) -> dict:
        return {
            "surah": self.surah,
            "ayah_start": self.ayah_start,
            "ayah_end": self.ayah_end,
            "score": round(self.score, 4),
            "words_matched": self.words_matched,
            "words_total": self.words_total,
            "surah_name": self.surah_name,
            "text": self.text,
        }


def load_corpus(path: str | Path) -> tuple[list[Verse], dict[int, str]]:
    """Load quran_verses.json → (verses, surah_name map)."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    verses = [
        Verse(
            surah=v["surah"],
            ayah=v["ayah"],
            text=v["text"],
            normalized=v["normalized"],
            words=v["normalized"].split(),
        )
        for v in payload["verses"]
    ]
    return verses, {int(k): v for k, v in payload.get("surah_names", {}).items()}


class VerseIndex:
    """In-memory corpus + word index with scoring and range alignment."""

    def __init__(self, verses: list[Verse], surah_names: dict[int, str] | None = None):
        self.verses = verses
        self.surah_names = surah_names or {}
        self._by_key = {(v.surah, v.ayah): v for v in verses}
        self._word_to_verses: dict[str, set[int]] = {}
        for i, v in enumerate(verses):
            for w in set(v.words):
                if len(w) >= 2:
                    self._word_to_verses.setdefault(w, set()).add(i)

    # -- candidate retrieval -------------------------------------------------

    def _candidates(self, words: list[str]) -> list[int] | None:
        """Verse indices sharing distinctive words with the transcript."""
        counts: dict[int, int] = {}
        for w in words:
            if len(w) < 2:
                continue
            for i in self._word_to_verses.get(w, ()):
                counts[i] = counts.get(i, 0) + 1
        if not counts:
            return None
        return sorted(counts)

    # -- scoring -------------------------------------------------------------

    @staticmethod
    def _align(verse_words: list[str], query_words: list[str]) -> tuple[int, int]:
        """(matched word count, last matched query index) via word-level LCS."""
        matcher = SequenceMatcher(None, verse_words, query_words, autojunk=False)
        matched = sum(b.size for b in matcher.get_matching_blocks())
        blocks = [b for b in matcher.get_matching_blocks() if b.size]
        last_q = blocks[-1].b + blocks[-1].size if blocks else 0
        return matched, last_q

    @staticmethod
    def _score(matched: int, n_query: int, n_verse: int) -> float:
        """Transcript coverage tempered by precision within the aligned span."""
        if n_query == 0:
            return 0.0
        coverage = matched / n_query
        precision = matched / n_verse if n_verse else 0.0
        return min(1.0, coverage * (0.5 + 0.5 * precision))

    @staticmethod
    def _char_score(query_norm: str, verse_norm: str) -> float:
        """Character-level fuzzy score.

        Fallback for ASR artifacts word matching can't see — most notably
        Whisper merging adjacent words into one token — where word-level
        exact tokens would score near zero. Coverage-dominant: a
        partial-verse query legitimately lives inside a long verse, so the
        size term only breaks ties against tiny verses.
        """
        if not query_norm or not verse_norm:
            return 0.0
        coverage = fuzz.partial_ratio(query_norm, verse_norm) / 100.0
        size_ratio = min(len(query_norm), len(verse_norm)) / max(
            len(query_norm), len(verse_norm)
        )
        query_coverage = min(1.0, len(verse_norm) / len(query_norm))
        return coverage * query_coverage * (0.75 + 0.25 * size_ratio)

    # -- public API ----------------------------------------------------------

    def _best_in_verse(self, words: list[str], verse: Verse) -> tuple[float, int, int]:
        blocks = [
            b for b in SequenceMatcher(
                None, verse.words, words, autojunk=False
            ).get_matching_blocks() if b.size
        ]
        if not blocks:
            return 0.0, 0, 0
        matched = sum(b.size for b in blocks)
        span_length = blocks[-1].a + blocks[-1].size - blocks[0].a
        last_q = blocks[-1].b + blocks[-1].size
        # Unspoken verse edges are not errors in a partial recording.
        return self._score(matched, len(words), span_length), matched, last_q

    def rank(self, transcript_words: list[str], top_k: int = 3) -> list[VerseMatch]:
        if not transcript_words:
            return []
        candidate_ids = range(len(self.verses))
        scored: list[tuple[float, int, int, int]] = []  # (score, matched, last_q, idx)
        query_norm = " ".join(transcript_words)
        for i in candidate_ids:
            verse = self.verses[i]
            score, matched, last_q = self._best_in_verse(transcript_words, verse)
            # Char-level fallback picks up ASR artifacts word matching
            # can't see — most notably Whisper merging adjacent words
            # into one token ("لمبعوثونَوَآبًا") and odd spellings. Damped
            # by word agreement so non-Quran text (zero shared words)
            # can't ride on character coincidence alone.
            agreement = 0.7 + 0.3 * min(1.0, matched / 2)
            score = max(score, self._char_score(query_norm, verse.normalized) * agreement)
            if matched or score > 0:
                scored.append((score, matched, last_q, i))
        scored.sort(key=lambda t: (-t[0], -t[1]))
        return [
            self._build_match(self.verses[i], transcript_words, s, m, lq)
            for s, m, lq, i in scored[:top_k]
        ]

    def _build_match(
        self, verse: Verse, transcript_words: list[str], score: float, matched: int, last_q: int
    ) -> VerseMatch:
        m = VerseMatch(
            surah=verse.surah,
            ayah_start=verse.ayah,
            ayah_end=verse.ayah,
            score=score,
            words_matched=matched,
            words_total=len(transcript_words),
            surah_name=self.surah_names.get(verse.surah),
            text=verse.text,
        )
        return m

    def identify(self, transcript_words: list[str], top_k: int = 3) -> list[VerseMatch]:
        """Rank ordered consecutive spans alongside individual verses."""
        if not transcript_words or top_k <= 0:
            return []
        singles = self.rank(transcript_words, top_k=max(top_k, 10))
        results = {(m.surah, m.ayah_start, m.ayah_end): m for m in singles}
        for i in self._candidates(transcript_words) or []:
            start = self.verses[i]
            span_words: list[str] = []
            owners: list[Verse] = []
            for ayah in range(start.ayah, start.ayah + _MAX_RANGE_VERSES):
                verse = self._by_key.get((start.surah, ayah))
                if verse is None:
                    break
                span_words.extend(verse.words)
                owners.extend([verse] * len(verse.words))
                if len(span_words) >= 2 * len(transcript_words) + 10:
                    break
            blocks = [
                b for b in SequenceMatcher(
                    None, span_words, transcript_words, autojunk=False
                ).get_matching_blocks() if b.size
            ]
            if not blocks:
                continue
            first = blocks[0].a
            last = blocks[-1].a + blocks[-1].size
            # Repeated ASR filler can align isolated common words in the
            # following ayah. Require consecutive evidence at range edges;
            # a canonical one-word ayah is still allowed.
            supported: set[int] = set()
            for block in blocks:
                run = 0
                previous_ayah = None
                for position in range(block.a, block.a + block.size):
                    owner = owners[position]
                    run = run + 1 if owner.ayah == previous_ayah else 1
                    previous_ayah = owner.ayah
                    if run >= min(2, len(owner.words)):
                        supported.add(owner.ayah)
            while first < last and owners[first].ayah not in supported:
                first += 1
            while last > first and owners[last - 1].ayah not in supported:
                last -= 1
            if first == last:
                continue
            first_verse, last_verse = owners[first], owners[last - 1]
            if first_verse.ayah == last_verse.ayah:
                continue
            matched = sum(
                max(0, min(last, b.a + b.size) - max(first, b.a)) for b in blocks
            )
            precision = matched / (last - first)
            coverage = matched / len(transcript_words)
            score = coverage * (0.5 + 0.5 * precision)
            m = VerseMatch(
                surah=start.surah,
                ayah_start=first_verse.ayah,
                ayah_end=last_verse.ayah,
                score=score,
                words_matched=matched,
                words_total=len(transcript_words),
                surah_name=self.surah_names.get(start.surah),
                text=" ".join(
                    self._by_key[(start.surah, a)].text
                    for a in range(first_verse.ayah, last_verse.ayah + 1)
                ),
            )
            key = (m.surah, m.ayah_start, m.ayah_end)
            if key not in results or m.score > results[key].score:
                results[key] = m
        return sorted(
            results.values(),
            key=lambda m: (-m.score, -m.words_matched, m.surah, m.ayah_start, m.ayah_end),
        )[:top_k]
