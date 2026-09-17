"""Tests for app.core.verse_match — real corpus (fast, no model)."""

from __future__ import annotations

import pytest

from app.core.arabic_norm import normalize_words
from app.core.config import get_settings
from app.core.verse_match import VerseIndex, load_corpus

pytestmark = pytest.mark.filterwarnings("ignore")


@pytest.fixture(scope="module")
def index() -> VerseIndex:
    verses, names = load_corpus(get_settings().verse_corpus_path)
    assert len(verses) == 6236
    return VerseIndex(verses, names)


def _identify(index: VerseIndex, text: str, top_k=3):
    return index.identify(normalize_words(text), top_k=top_k)


def test_exact_single_verse(index):
    m = _identify(index, "قل هو الله احد")
    assert m[0].surah == 112 and m[0].ayah_start == 1
    assert m[0].score >= 0.99


def test_full_verse_with_diactritics_in_corpus_terms(index):
    # Ikhlas 2 with one ASR-style misspelling (الصمد vs الصمد is same;
    # use a real typo: "الصمد" → "الصمد" ok, use "صمد")
    m = _identify(index, "الله الصمد")
    assert m[0].surah == 112 and m[0].ayah_start == 2


def test_ayah_range_across_boundary(index):
    m = _identify(index, "الحمد لله رب العالمين الرحمن الرحيم مالك يوم الدين")
    top = m[0]
    assert (top.surah, top.ayah_start, top.ayah_end) == (1, 2, 4)
    assert top.words_matched == top.words_total == 9
    assert top.score <= 1.0


def test_partial_verse_start(index):
    # Second half of 2:255 (Ayat al-Kursi)
    m = _identify(index, "لا تاخذه سنه ولا نوم")
    assert m[0].surah == 2 and m[0].ayah_start == 255
    assert m[0].score > 0.5


def test_repeated_phrase_ambiguous_still_in_top_k(index):
    m = _identify(index, "فباي آلاء ربكما تكذبان")
    assert m[0].surah == 55 and m[0].ayah_start == 13
    assert len(m) == 3 and all(x.surah == 55 for x in m)


def test_non_quran_text_below_confidence_threshold(index):
    # Must fall under the API's confidence gate (verse_score_threshold).
    m = _identify(index, "ذهبت الى السوق في الصباح الباكر لشراء الخضار")
    from app.core.config import get_settings

    assert not m or m[0].score < get_settings().verse_score_threshold


def test_empty_transcript(index):
    assert index.identify([], top_k=3) == []


def test_top1_beats_top2(index):
    m = _identify(index, "اننا انزلناه في ليلة القدر")
    assert m[0].score > m[1].score
    assert (m[0].surah, m[0].ayah_start) == (97, 1)


def test_surah_names_loaded(index):
    assert index.surah_names[112] == "الاخلاص"


@pytest.mark.parametrize("surah,start,end", [(112, 1, 4), (55, 1, 6), (1, 2, 7), (97, 1, 5)])
def test_complete_short_surah_ranges(index, surah, start, end):
    text = " ".join(index._by_key[(surah, a)].text for a in range(start, end + 1))
    top = _identify(index, text)[0]
    assert (top.surah, top.ayah_start, top.ayah_end) == (surah, start, end)
    assert top.words_matched == top.words_total
    assert top.score == 1.0


def test_middle_verse_does_not_hide_partial_start(index):
    verses = [index._by_key[(1, a)] for a in range(2, 5)]
    words = verses[0].words[-2:] + verses[1].words + verses[2].words[:2]
    top = index.identify(words)[0]
    assert (top.surah, top.ayah_start, top.ayah_end) == (1, 2, 4)


def test_short_subset_cannot_explain_long_transcript(index):
    assert index._char_score("الله الصمد كلام مختلف طويل جدا", "الله الصمد") < 0.5


@pytest.mark.parametrize("text", [
    "يعلم ما بين ايديهم وما خلفهم ولا يحيطون بشي من علم",
    "يعلم ما بين ايديهم وما خلفهم ولا يحيطون بشي",
])
def test_real_audio_kursi_excerpt_beats_shared_phrase(index, text):
    top = _identify(index, text)[0]
    assert (top.surah, top.ayah_start, top.ayah_end) == (2, 255, 255)


def test_shared_partial_phrase_has_no_unique_location(index):
    matches = _identify(index, "ما بين ايديهم وما خلفهم ولا يحيطون")
    assert matches[0].score - matches[1].score < 0.05


def test_repeated_asr_tail_does_not_add_unheard_ayah(index):
    top = _identify(
        index,
        "فباي الاء ربكما تكذبان فباد فباد خلق الانسان من صلصال من صلصال من صلصال",
    )[0]
    assert (top.surah, top.ayah_start, top.ayah_end) == (55, 13, 14)
