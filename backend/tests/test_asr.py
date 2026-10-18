"""ASR segment assembly regression; no model download required."""
from types import SimpleNamespace

import numpy as np

from app.core import asr


def test_segment_boundaries_keep_separate_words(monkeypatch):
    options = {}

    class Model:
        def transcribe(self, audio, **kwargs):
            options.update(kwargs)
            return iter([
                SimpleNamespace(text="first", words=None),
                SimpleNamespace(text="second", words=None),
            ]), None

    monkeypatch.setattr(asr, "get_model", lambda: Model())
    text, words = asr.transcribe_waveform(np.zeros((1, 16000), dtype=np.float32))
    assert text == "first second"
    assert words == []
    assert options["word_timestamps"] is False
    assert options["beam_size"] == 5
