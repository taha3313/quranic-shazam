"""Tests for app.core.arabic_norm."""

from __future__ import annotations

from app.core.arabic_norm import normalize_arabic, normalize_words


def test_strips_diacritics():
    assert normalize_arabic("ٱلرَّحۡمَٰنِ") == normalize_arabic("الرحمن")


def test_unifies_alef_variants():
    assert normalize_arabic("أحمد إبراهيم") == normalize_arabic("احمد ابراهيم")
    assert normalize_arabic("ٱللَّه") == normalize_arabic("الله")


def test_dagger_alef_stripped():
    # Corpus is Imla'i; ASR output never contains dagger alef, so U+0670
    # is stripped like any mark (Uthmani الرَّحۡمَٰنِ → الرحمن).
    assert normalize_arabic("ٱلرَّحۡمَٰنِ") == "الرحمن"


def test_standalone_hamza_dropped():
    assert normalize_arabic("ءالاء") == normalize_arabic("الاء")


def test_ta_marbuta_and_maqsura():
    assert normalize_arabic("جامعة") == normalize_arabic("جامعه")
    assert normalize_arabic("على") == normalize_arabic("علي")


def test_spaces_preserved():
    words = normalize_words("قل هو الله احد")
    assert words == ["قل", "هو", "الله", "احد"]


def test_empty_and_punctuation():
    assert normalize_arabic("") == ""
    assert normalize_arabic("١٢٣ ,.") == ""


def test_tatweel_removed():
    assert normalize_arabic("ر----ب") == normalize_arabic("رب")


def test_line_breaks_preserve_token_boundaries():
    assert normalize_words("قل\nهو\tالله\r\nاحد") == ["قل", "هو", "الله", "احد"]
