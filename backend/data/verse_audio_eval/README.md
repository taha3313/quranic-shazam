# Real-audio verse recognition check — 2026-09-17

Actual cached Quranic Whisper int8 CPU model, real EveryAyah recordings.
Three reciters: Alafasy, Husary, Minshawi. Source ayah IDs provide labels.

27 cases per run: 18 distinct single-ayah recordings, three 8-second
mid-verse Ayat al-Kursi crops, three concatenated Ikhlas 112:2-4 ranges,
and three ambiguous Rahman 55:13 refrain recordings.
Long single-ayah uploads are processed only through the first 20 seconds.

Baseline: 21/24 non-refrain top-1 answers correct; three confident errors.
After aligned-span precision fix: 24/24 top-1 answers correct; zero confident
errors. 18/24 non-refrain cases marked confident; six marked uncertain.
All three repeated refrains also marked uncertain.

The partial crops now rank 2:255 first but remain uncertain. In Minshawi's
crop, ASR produces only a phrase shared with other ayahs; matching the source
label is not proof that the location can be uniquely determined.
Whisper adds hallucinated words on several clean single-ayah clips, reducing
confidence on three otherwise correct answers.

This small suite was used to diagnose and fix a bug; it is not an independent
test-set accuracy estimate. EveryAyah may overlap the model's training data.
Ranges concatenate independently recorded ayahs, rather than uninterrupted
recitation. Phone microphones, noise and non-Quran audio were not tested.

Reproduce from backend:
    .venv/bin/python -m scripts.evaluate_verse_audio

results_before.json preserves baseline.
results.json contains final transcripts, candidates, confidence, source URLs
and timing for every case. No ASR stubs were used.
