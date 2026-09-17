"""ASR segment assembly regression; no model download required."""
from types import SimpleNamespace

import torch

from app.core import asr


def test_segment_boundaries_keep_separate_words(monkeypatch):
    class Model:
        def transcribe(self, audio, **kwargs):
            return iter([
                SimpleNamespace(text="first", words=None),
                SimpleNamespace(text="second", words=None),
            ]), None

    monkeypatch.setattr(asr, "get_model", lambda: Model())
    text, words = asr.transcribe_waveform(torch.zeros(1, 16000))
    assert text == "first second"
    assert words == []
