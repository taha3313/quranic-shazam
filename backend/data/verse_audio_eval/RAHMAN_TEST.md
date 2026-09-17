# Rahman repeated-ayah real-audio check — 2026-09-17

24/24 cases passed with actual Quranic Whisper int8 CPU inference.

Three reciters: Alafasy, Husary, Minshawi.
Four corpus-verified refrain positions: 55:16, 55:30, 55:59, 55:77.

12 refrain-only recordings: all uncertain and requesting more audio.
Their first displayed candidate may be 55:13 because all refrain occurrences
share identical text; that is not an identification of the actual occurrence.

12 refrain-plus-following-ayah recordings: all confident and correctly
identifying 55:16-17, 55:30-31, 55:59-60 or 55:77-78.
No confidently wrong locations or range boundaries in these 24 cases.

Additional regression coverage: all 31 canonical refrain positions remain
ambiguous without context; four positions resolve when next-ayah text is
added. All eight continued-listening regression tests passed.

Source-labelled EveryAyah MP3 recordings; pairs concatenate independent
real ayah recordings. These are targeted smoke tests, not a broad accuracy
estimate. Training overlap is possible. Physical browser microphones,
background noise and codec streams were not tested in this suite.
Source URLs, full transcripts, competing matches, scores, confidence,
processed duration and latency are in rahman_results.json.

Run fresh from backend:
    .venv/bin/python -m scripts.evaluate_rahman_audio

For an interrupted unchanged run only:
    .venv/bin/python -m scripts.evaluate_rahman_audio --resume
