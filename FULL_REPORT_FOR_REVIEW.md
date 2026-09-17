# Quranic Shazam — Full Technical Report for Review

> Copy-paste this entire document into ChatGPT for further review. It is self-contained. Repo: `~/quranic-shazam` (WSL Ubuntu). Branch `main`, head `42268e3`. Verse-ID feature exists as **uncommitted work** on top of committed 20-reciter system.

## 1. What it is

**Quranic Shazam**: given a short audio clip of Quran recitation, identify:
1. **Who** is reciting (closed-set, 20 famous reciters) — `POST /identify_reciter`, `WS /live_reciter`.
2. **What** is being recited (surah + ayah range) — `POST /identify_verse` (new, uncommitted).

Browser frontend: upload file OR live mic recording. Backend: FastAPI + CPU-only ML. No GPU, no training on Quran data.

**Measured results (reciter): 97.31% top-1 (760/781), 99.10% top-3, 99.62% top-5 across 20 reciters on held-out surahs, p50 ~1.3s/clip CPU.**

## 2. Features implemented

### 2.1 Reciter identification (upload) — `POST /identify_reciter?top_k=3`
Input: multipart audio (mp3/wav/ogg/webm/opus), ≤25MB, first 30s used.
Output: `{matches: [{reciter: key, display: human name, score: cosine -1..1}]}` ranked desc.
Flow: stream-capped read → `soundfile` decode (ffmpeg fallback) → 16kHz mono → trim → ECAPA-TDNN embed (192-d) → cosine vs 20 profiles → top-k.

### 2.2 Live reciter recognition — `WS /live_reciter`
Client: `MediaRecorder(audio/webm;codecs=opus)`, `start(300)` → 300ms binary chunks over WS.
Server: accumulates raw bytes, dual-strategy decode (see §5.4), every ~3 chunks embeds 5s sliding window. If top-1 ≥0.85 (configurable) replies `{matches:[...]}` and slides window; if 30s elapsed without confidence replies `{matches:[{reciter:"Not sure", score:0}]}`. Error frames: `{error:...}`.
Frontend hook: `useLiveReciter.ts` (getUserMedia, WS lifecycle, cleanup).

### 2.3 Verse identification (upload) — `POST /identify_verse?top_k=3&include_transcript=false` (UNCOMMITTED)
Input: same upload caps, first 20s used.
Pipeline: decode → faster-whisper ASR (`OdyAsh/faster-whisper-base-ar-quran`, CT2 int8, CPU) → Arabic normalization → inverted-index retrieval + word-LCS + char-fuzzy scoring → ayah-range extension.
Output: `{transcript?, confident: bool (top1≥0.55), matches: [{surah, surah_name, ayah_start, ayah_end, score, words_matched, words_total, text}]}`.
Corpus: `backend/data/quran_verses.json` (6236 verses, Tanzil Simple-Clean Imla'i via alquran.cloud, built by `scripts/build_verse_corpus.py`).
No live verse WS yet (planned).

### 2.4 Frontend — React + Vite + TypeScript + Tailwind
Tabs: `Identify Reciter` / `Identify Verse` (`App.tsx`).
Components: `IdentificationForm` (file upload + player), `VerseForm` (new, uncommitted), `Result`, `useLiveReciter`.
`api.ts`: `API_BASE_URL` from `VITE_API_URL`, `WS_BASE_URL` derived (wss if https), `identifyReciter()`, `identifyVerse()`. `types.ts`: `ReciterMatch`, `IdentifyResponse`, `VerseMatch`, `IdentifyVerseResponse`.
Build: `tsc -b && vite build`, served by nginx :8080 in Docker.

### 2.5 Offline pipeline + evaluation
`scripts/sources.py` → `generate_data.py` (download+split) → `extract_embeddings.py` (profiles) → `evaluate.py` (simple top-1) → `evaluate_report.py` (deep: confusion matrix, top-k, margins, per-surah/duration, latency, JSON+MD to `data/eval_reports/`).
`scripts/build_verse_corpus.py` (verse corpus fetch/clean).

### 2.6 Ops
`GET /health → {status, reciters_loaded, model_loaded}`. Lifespan warms profile DB, optional model warm-up. Docker Compose: backend :8000 + frontend :8080, HF/torch cache volumes, healthcheck. Makefile wraps all tasks. 23+ backend pytest tests (no heavy model), ruff, `tsc --noEmit`.

## 3. Architecture

```text
                  ┌─────────────────────────────────────────┐
                  │ OFFLINE PIPELINE                        │
quranicaudio.com ─┤ sources.py (URL templates)              │
surahquran.com  ──┤ generate_data.py (download+split 10s/5s)│
mp3quran CDN      │ extract_embeddings.py → *.npy (20x192)  │
alquran.cloud ────┤ build_verse_corpus.py → quran_verses.json│
                  │ evaluate.py / evaluate_report.py        │
                  └─────────────────────────────────────────┘
Browser (React+TS, Vite/:5173 or nginx/:8080)
  POST /identify_reciter ──────────▶ FastAPI :8000
  WS   /live_reciter ══════════════▶  route → to_thread decode →
  POST /identify_verse ───────────▶  to_thread ECAPA/ASR → cosine/text rank
                                      app/services/{reciter,verse}_service
                                      app/core/{audio,embeddings,asr,
                                        similarity,arabic_norm,verse_match,config}
```

Backend layering (strict): `api/routes` (thin, async) → `services` (stateful singletons, semaphores) → `core` (pure helpers). Request path never imports `scripts/`. Frontend never embeds ML.

Deployment: single uvicorn worker (correct for CPU-bound torch), `docker-compose.yml` backend+frontend, CPU torch wheel index.

## 4. Tools / stack + versions

| Layer | Tool | Decision/Version |
|---|---|---|
| Backend | FastAPI 0.111–0.120, uvicorn[standard], pydantic v2 + pydantic-settings (`QD_` prefix) | async routes + `anyio.to_thread` for blocking work |
| Reciter ML | SpeechBrain 0.5.13 `spkrec-ecapa-voxceleb` (VoxCeleb), 192-d | frozen extractor, mean profile, cosine; `huggingface_hub<0.26` pin (newer removed `use_auth_token` breaking SpeechBrain) |
| Verse ASR | faster-whisper <1.2 + `OdyAsh/faster-whisper-base-ar-quran` (CT2 of `tarteel-ai/whisper-base-ar-quran`), int8 CPU, beam 5, `language=ar`, word_timestamps | chose base over small/large: Apache-2.0, 74M/141MB, fastest CPU, best unseen-reciter WER 8.7; fallback `basharalrfooh/whisper-small-quran` (MIT) if needed; rejected CC BY-NC models |
| Verse match | rapidfuzz ≥3.14.5 + difflib SequenceMatcher | word-LCS coverage*precision + char `partial_ratio` fallback |
| Audio | soundfile ≥0.12 primary, torchaudio CPU fallback, ffmpeg binary fallback, pydub split | torchaudio≥2.9 dropped decoders → soundfile-first |
| Numerics | numpy<2, scipy, torch ≥2.1 CPU index, torchcodec 0.8.1, onnxruntime<1.21 | CPU-only wheels via `uv` |
| Data fetch | requests, tqdm, stdlib urllib | ThreadPool 4 downloads |
| Dev | `uv` + `uv.lock` (py3.10–3.12), `make`, ruff (E,F,I,UP,B), pytest + httpx, WSL2 Ubuntu, `.gitattributes` LF | reproducible, no pip |
| Frontend | React, Vite, TypeScript (`tsc --noEmit` clean), Tailwind, nginx Docker, `VITE_API_URL`/`VITE_WS_URL` | JSX→TS migration for contract safety |
| Corpus text | alquran.cloud `quran-simple-clean` (Tanzil Simple-Clean Imla'i) | Imla'i not Uthmani to match ASR orthography; BOM/basmala/surah-name quirks handled |

Config (`app/core/config.py`, env `QD_`): `data_dir`, `embeddings_path`, `sample_rate=16000`, `embedding_model_source`, `warm_model`, `cors_origins`, `max_upload_mb=25`, `max_audio_sec=30`, `top_k_default=3`, `live_window_sec=5`, `live_max_duration_sec=30`, `live_confidence_threshold=0.85`, `verse_corpus_path`, `asr_model_source/device/compute_type`, `verse_max_audio_sec=20`, `verse_score_threshold=0.55`, `clip_duration_ms=10000`, `clip_overlap_ms=5000`.

## 5. System design details

### 5.1 Data sources (`scripts/sources.py`)
`ReciterSpec` registry = single source of truth (key, display, qa_id, sq_slug, cdn_code). `reciters.json` generated from it.
- Primary: `quranicaudio.com` → `https://download.quranicaudio.com/quran/{slug}/{NNN}.mp3`, slug scraped once per reciter (handles subfolders `maher_almu3aiqly/year1440/`, `sa3d_al-ghaamidi/complete/`, `kurdi/mp3/`). 18/20 reciters.
- Fallback: `surahquran.com` scraping → mp3quran `server6.../abkr/` (Idris Abkar), `.../aloosi/` (Al-Ossi). Reason: Abkar quranicaudio archive polluted with other voices; Ossi absent.
- Legacy islamic.network CDN kept.

20 reciters: abdulbaset, minshawi, husary, mustafa, banna, sudais, shuraim, maher, juhany, dosari, alafasy, ghamdi, ajmy, qatami, hani, abkar, fares, kurdi, tunaiji, ossi.

### 5.2 Dataset
Train surahs 36/55/56/67, eval surahs 78/87/93/112 — strictly disjoint. Whole-surah MP3 → 10s clips 5s overlap (pydub) → ~12,500 wavs ~19GB gitignored, resumable, 4-thread. Eval audio re-downloaded fresh at eval time (honest but fragile).

### 5.3 Profiles (`extract_embeddings.py`)
≤80 clips/reciter **round-robin across train surahs** → embed each → mean-pool → `reciters_embeddings.npy` (~20KB dict). Round-robin is load-bearing: sorted-first-80 = single surah → collapse 100%→<10%.

### 5.4 Serving path
- Upload: `_read_capped` streams 1MiB chunks, 413 past cap *before* buffering all. `anyio.to_thread.run_sync(identify_upload_bytes)` → decode → trim → `Semaphore(2)` → ECAPA → `rank_reciters` (L2-norm cosine, skips shape-mismatch). Errors: 400 empty/garbage, 413 oversize, 503 no DB, 500 logged.
- Live WS: `_decode_step` tries per-chunk decode (wav frames); only if *all* pending fail (webm headerless continuation signature) decodes cumulative `raw_all` buffer. Caps raw buffer 10MB. Decode+identify in threads. `consumed`/`identified_samples` offsets prevent re-scoring.
- Singletons: ECAPA lazy thread-safe (`_lock` + `_classifier`), `is_loaded()` for health; profile DB lazy + lock + `reciters.json` display names; ASR lazy singleton + `Semaphore(1)`; verse index lazy + lock.
- `audio.py`: `to_mono`, resample via `torchaudio.functional`, `normalize`, `load_audio_file` (soundfile→torchaudio fallback), `decode_upload_bytes` (soundfile→ffmpeg pipe:0→wav pipe:1, 10s timeout), `ensure_min_length` pads <1s with 1e-4 noise, `save_upload_to_temp`.

### 5.5 Verse stack
`arabic_norm.py`: NFKC, map ٱأإآ→ا, ى→ي, ة→ه, drop ء/ـ, strip Mn/Me (tashkeel/waqf), keep L+Zs, collapse spaces. `verse_match.py`: `Verse`/`VerseMatch` dataclasses, `load_corpus`, `VerseIndex` with word→verse inverted index (len≥2), `_candidates`, `_align` (word LCS via SequenceMatcher autojunk=False → matched,last_q), `_score=coverage*(0.5+0.5*precision)`, `_char_score=partial_ratio*(0.75+0.25*size_ratio)`, `rank` (max(word,char*agreement 0.7+0.3*min(1,matched/2))), `identify` + `_with_range` (tail≥3 words, continuation coverage≥0.6, max +4 verses, recompute score max). `verse_service.py`: `identify_transcript` (pure text), `identify_waveform` (ASR+match), `identify_upload_bytes` (decode+20s trim+semaphore). `asr.py`: `transcribe_waveform` (float32 numpy → faster-whisper, returns text+words).

## 6. Every key decision + rationale

1. **Embedding matching > training classifier**: zero training/GPU, add-reciter = add profile, VoxCeleb timbre transfers to clean recitation; cost: single mean brittle for mujawwad/murattal splits (abdulbaset 77.5%).
2. **ECAPA-TDNN VoxCeleb frozen**: proven speaker verification, 192-d, CPU ~1s.
3. **Mean profile + cosine over ANN**: 20 vectors = microseconds numpy; no vector DB.
4. **Round-robin sampling**: fixes single-surah overfit.
5. **Source swap not clustering for pollution**: per-surah vote diagnostics found Abkar pollution (s36 226/227 self, others 0); k-means dominant-voice filter hurt (abdulbaset 77.5→62.5) → reverted, swapped to mp3quran.
6. **soundfile + ffmpeg fallback**: torchaudio backend removal + browser webm/opus reality.
7. **Lazy singletons + optional `QD_WARM_MODEL`**: fast import/tests, fail-fast optional, first-request cost avoided when enabled.
8. **Off-loop inference (`to_thread` + Semaphore(2) reciter / 1 verse)**: audit C1 — async route blocked loop ~1.3s freezing health+WS; heartbeat test proved (0 ticks pre-fix). Semaphore prevents torch thrash.
9. **Stream-capped uploads + 30s/20s trims**: H1/H2 — `await file.read()` then check = RAM DoS; 25MB mp3 = hours CPU DoS. Verse 20s tighter (Whisper degrades >30s, ranges need clean counts).
10. **Dual-decode live WS**: audit C2 — per-chunk webm decode impossible (header only chunk 1) → cumulative fallback, proven with 7-chunk ffmpeg webm test.
11. **App-owned `reciters.json` (H6)**: request path no longer imports `scripts/`.
12. **uv + CPU index + pins**: reproducible; `huggingface_hub<0.26`, `torchcodec==0.8.1`.
13. **TS frontend + env URLs + nginx**: contract safety (`ReciterMatch{display?}`), dev/prod URL switch, Docker :8080.
14. **Single uvicorn worker**: correct for CPU-bound; documented.
15. **Honest disjoint eval + frozen 97.31% baseline**: no tuning on eval surahs; `evaluate_report.py` reproduces exactly.
16. **Verse: tarteel-base + faster-whisper int8**: license/size/speed/ecosystem; CT2 third-party (OdyAsh) pinned with transformers fallback noted.
17. **Verse: Imla'i corpus + custom normalization**: matches ASR orthography; avoids Uthmani mismatch.
18. **Verse: retrieval (index) + alignment (LCS) + char fallback + range extension**: handles partial verses, Whisper word-merge artifacts, multi-verse spans, repeated-phrase surahs via precision damping; threshold+margin for unknown (absolute threshold alone insufficient — wrong reaches 0.636, weakest correct 0.238).
19. **No refactor-everything rule**: system frozen, every change measured vs baseline.

## 7. Audit → fixes (commits)

- `cd2889d`: 20-reciter pipeline refactor.
- `63939b1`: C1 thread offload + semaphore + 21-test suite (heartbeat concurrency regression).
- `4de473f`: C2 dual decode, H1/H2 caps, H4 warm-up, H6 app metadata, M2/M4.
- `4ea579b`: deep eval harness.
- Uncommitted: verse ASR stack + `AYAH_ID_RESEARCH.md` + frontend Verse tab.
- AUDIT.md left C1/C2/H1-H6/M1-M10/L1-L2; M5/M6/M7/M8 still open (no structured logging, root container, 80MB models in git, no frozen eval manifest).

## 8. Results

Held-out 78/87/93/112, 781 clips: abdulbaset 77.5, husary 85.4, hani 92.7, shuraim 97.1, dosari 97.3, kurdi 97.6, 14×100% (incl. abkar after fix). Overall 97.31/99.10/99.62, p50 1.34s.
Deep: 21 errors in 3 pairs (abdulbaset↔dosari/banna 8+1, husary→abdulbaset 6, hani→ossi 3 +3 singletons); abdulbaset top-3 97.5% → discrimination not retrieval; 5s clips 93.6% (−3.7 vs 10s) → live window penalty.

## 9. Repo map + API

```text
backend/app/{main,api/routes/{reciter,live_reciter,verse*},api/schemas,core/{audio,embeddings,asr*,arabic_norm*,verse_match*,similarity,config},services/{reciter,verse*}_service}
backend/scripts/{sources,generate_data,extract_embeddings,evaluate,evaluate_report,build_verse_corpus*}
backend/tests/{test_api,test_audio,test_concurrency,test_identification_api,test_live_websocket,test_arabic_norm*,test_verse_match*,test_verse_api*} (*=uncommitted)
backend/data/{reciters.json,reciters_embeddings.npy,recitations_clips/(gitignored),quran_verses.json*,eval_reports/}
frontend/src/{api,types,App,hooks/useLiveReciter,components/{IdentificationForm,Result,VerseForm*}}
docker-compose.yml, Makefile (backend-install/dev/run/test/lint, data/embeddings/evaluate, frontend-*, docker-*), PROJECT_DESIGN.md, PROJECT_REPORT.md, AUDIT.md, docs/AYAH_ID_RESEARCH.md
```

API: `POST /identify_reciter`, `POST /identify_verse`, `WS /live_reciter`, `GET /health` — see §2 for schemas.

## 10. Limitations + roadmap for reviewer

Weak: AI-assisted code, thin review, no compose integration test; same-archive train/eval channel bias (foreign mics/YouTube/phone unmeasured); 781 clips small (±3–7pt); 19GB clips + models in git/fragile URLs; closed-set always answers; live threshold hand-tuned uncalibrated; verse accuracy unmeasured.
Roadmap order: 1-3 done (audit/fix/harness) → 4 multi-profile k-means k=2..5 + style split (next) → 5 unknown rejection (threshold+margin + OOD protocol) → 6 auto per-surah vote/near-dup diagnostics → 7 robustness (noise/reverb/codec/phone/duration) → 8 hardening (non-root, limits, logging/IDs, ffmpeg timeouts, frozen manifest+checksums) → 9 risk-based tests. Rule: beat frozen baseline.

## 11. Repro

```bash
cd ~/quranic-shazam
make backend-install; make backend-test; make backend-dev # :8000
make data; make embeddings; make evaluate
cd backend && uv run python -m scripts.evaluate_report
cd backend && uv run python scripts/build_verse_corpus.py # verse only
make frontend-install; make frontend-dev # :5173, VITE_API_URL=http://127.0.0.1:8000
make docker-up # :8000+:8080
```

Review focus requested: serving concurrency correctness, live WS decoder, verse matching robustness, eval honesty, extensibility, security/caps, test gaps.
