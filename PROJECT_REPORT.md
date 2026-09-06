# Quranic Shazam — Full Project Report

> "Shazam for Quran recitation": upload or stream a short clip of Quran recitation and the system tells you which of 20 well-known reciters is performing.
>
> This report is a complete, self-contained account of the project — history, approach, architecture, data engineering, results, engineering audit and fixes, and the experiment roadmap — written to hand to another AI (or engineer) for deeper analysis. Reproducibility notes and known limitations are included; the tone is deliberately honest about what is strong and what is not.

---

## 1. History and how the project evolved

### v0 — the 3-reciter prototype ("vibecoded")
The first version was built AI-assisted, experimentally, without a rigorous plan: 3 reciters (Abdul Basit, Minshawi, Husary), clips pulled from the islamic.network CDN, a single FastAPI endpoint, a React upload form, and the same core idea that survives today — **pretrained speaker embeddings + cosine matching against a mean voice print per reciter**. It worked surprisingly well for 3 reciters, which validated the core bet before any infrastructure existed. Problems: ad-hoc scripts at the repo root, temp files committed to git, no held-out evaluation, no source diversity, no tests beyond a smoke check.

### v1 — production-oriented refactor (still AI-assisted, now with structure)
The codebase was reorganized deliberately: `app/core` (audio, embeddings, similarity, config), `app/api` (routes, schemas), `app/services` (profile DB + identification), `scripts/` (data pipeline), `tests/`. Python deps moved to **uv** with a lockfile and CPU-only PyTorch wheels; frontend moved **JSX → TypeScript**; Docker/compose, Makefile, ruff, pytest added. A WebSocket live-recognition mode (mic streaming) was added. This is commit `59cd7cd` and earlier.

### v2 — 20-reciter expansion (this phase, the bulk of this report)
The objective: scale from 3 to 20 reciters with **honest evaluation** (surahs held out from profile building), a multi-source data pipeline, and a reproducible harness. This phase produced:

| commit | content |
|---|---|
| `cd2889d` | 20-reciter dataset + quranicaudio/surahquran source pipeline, embeddings DB, refactor, naming consistency |
| `63939b1` | Serving-path audit fixes: inference off the event loop, semaphore, 21-test suite |
| `4de473f` | Live webm streaming fix, upload size/duration bounds, warm-up, app-owned metadata |
| `4ea579b` | Deep evaluation harness (confusion matrix, top-k, margins, JSON+MD reports) |

**Headline result: 97.31% top-1 accuracy over 781 held-out eval clips across 20 reciters** (760/781), top-3 99.10%, top-5 99.62%, on CPU with a pretrained model and zero training.

---

## 2. Problem framing and why this approach

**Task:** closed-set reciter identification from ~10 s of audio, 20 classes, CPU-only deployment.

**Chosen approach — speaker verification machinery, not classification training:**
- Use **SpeechBrain ECAPA-TDNN** (`speechbrain/spkrec-ecapa-voxceleb`), pretrained on VoxCeleb, as a **frozen feature extractor** producing 192-dim speaker embeddings.
- Per reciter, embed ~80 training clips and **mean-pool** into one 192-dim "voice print" profile.
- Query = embed → **cosine similarity** vs all 20 profiles → ranked matches.

**Why this instead of training a classifier:**
1. Zero Quran-specific training data engineering (no labels bookkeeping, no training loop, no GPU).
2. Adding reciter = download clips + append a profile; no retraining, no catastrophic forgetting.
3. ECAPA captures timbre (vocal tract, phonation) that is reciter-specific regardless of language — and recitation audio is clean, slow, single-speaker, i.e. *easier* than VoxCeleb's noisy celebrity speech. The domain gap turned out not to matter (97%+ without any adaptation).
4. A 20-entry profile DB needs no ANN index; numpy cosine over 20 vectors is microseconds.

The known cost of this design: one mean vector per reciter is brittle for reciters with strongly different styles (mujawwad vs murattal) — visible in the results (§7) and the target of experiment #4 (§10).

---

## 3. System architecture

```
                    ┌─────────────────────────────────────────────┐
                    │           OFFLINE DATA PIPELINE             │
                    │                                             │
 quranicaudio.com ─┐│  scripts/sources.py        URL resolution   │
 surahquran.com  ──┤├─▶scripts/generate_data.py download+split   │
 (mp3quran CDN)     ││  scripts/extract_embeddings.py             │
                    ││       └─▶ data/reciters_embeddings.npy     │
                    ││  scripts/evaluate.py        accuracy       │
                    ││  scripts/evaluate_report.py deep reports   │
                    │└─────────────────────────────────────────────┘
 Browser (React+TS) ▼
┌──────────────┐ POST /identify_reciter (multipart audio)
│   Frontend   │──────────────────────▶┌───────────────────────────────┐
│ Vite build / │  JSON matches[]       │ FastAPI backend (uv, :8000)   │
│ nginx (:8080)│◀──────────────────────│  route → (thread) decode →    │
└──────────────┘                       │  (thread) ECAPA → cosine rank │
┌──────────────┐ WS /live_reciter     │  app/services/reciter_service │
│  Live mic    │═════════════════════▶│  app/core/{audio,embeddings,  │
│  MediaRecorder│ streaming windows,   │           similarity,config}  │
└──────────────┘ stops at confidence  └───────────────────────────────┘
```

Deployment: `docker-compose.yml` — backend (:8000, uvicorn, single worker — correct for CPU-bound inference), frontend (:8080 nginx), HF cache volumes, healthcheck on `/health`.

### Request flow (upload)
1. Route streams the upload in 1 MiB chunks, rejecting past `QD_MAX_UPLOAD_MB` (25) **before** buffering everything.
2. In a worker thread (`anyio.to_thread.run_sync`): decode via **soundfile** (16 kHz mono float32), ffmpeg subprocess fallback for webm/opus; trim to `QD_MAX_AUDIO_SEC` (30 s).
3. In a worker thread, under a `Semaphore(2)`: ECAPA forward pass → 192-dim vector.
4. `rank_reciters`: cosine vs 20 profiles, returns top-k with `{reciter, display, score}`.

### Live mode (WebSocket)
Client streams MediaRecorder chunks (webm/opus, 300 ms). Server buffers raw bytes and uses a **dual decode strategy**: per-chunk decode when chunks are self-contained (raw wav), **cumulative whole-buffer decode with a consumed-samples offset** when they are not (webm — the container header exists only in chunk 1). Every ~3 chunks it decodes; once ≥ `live_window_sec` (5 s) of audio is decoded it embeds the window; if top-1 cosine ≥ `live_confidence_threshold` (0.85) it replies with the result and slides the window, otherwise it keeps accumulating until `live_max_duration_sec` (30 s) and then answers "Not sure".

### Model handling
Lazy, thread-safe singleton for ECAPA (`app/core/embeddings.py`); optional `QD_WARM_MODEL=1` loads it at startup in a thread so the first request is fast and a broken cache fails at boot. Profile DB (a ~20 KB `.npy` dict) loads once under a lock; reciter display names load from `data/reciters.json` — the request path has **no dependency on `scripts/`**.

---

## 4. The data pipeline (where most of the engineering lives)

### Sources (`scripts/sources.py`)
- **Primary: quranicaudio.com** — `https://download.quranicaudio.com/quran/{slug}/{NNN}.mp3`. The per-reciter slug (sometimes with a subfolder like `maher_almu3aiqly/year1440/` or `sa3d_al-ghaamidi/complete/`) is scraped once from the reciter page and cached as a URL template. 18 of 20 reciters are served this way.
- **Fallback: surahquran.com** — scrapes the mp3 URL (hotlinks mp3quran.net/archive.org). Used for Al-Ossi (`server6.mp3quran.net/aloosi/`) and Idris Abkar (`server6.mp3quran.net/abkr/`).
- `ReciterSpec` registry (key, display name, qa_id, sq_slug, legacy cdn_code) is the **single source of truth** for reciter identity; `reciters.json` is generated from it so API display names and metadata can never drift apart.

### Dataset
- **Train surahs: 36, 55, 56, 67.** **Eval surahs: 78, 87, 93, 112** — strictly disjoint; eval audio is re-downloaded fresh at evaluation time.
- Whole-surah MP3s are split into **10 s clips with 5 s overlap** (pydub) → ~12,500 wav clips, ~19 GB on disk, zero download failures. Resume support (existing surahs skipped), 4-thread pool.

### Profile building (`scripts/extract_embeddings.py`)
- Up to **80 clips per reciter, sampled round-robin across the training surahs**, embedded and mean-pooled.
- The round-robin is load-bearing: taking "first 80 sorted" pulled every clip from the single longest surah and collapsed one reciter's accuracy from ~100% to under 10% (§6.2).

### Evaluation (`scripts/evaluate.py`, `scripts/evaluate_report.py`)
- `evaluate.py`: simple top-1 harness (the baseline number).
- `evaluate_report.py`: the deep harness — per-clip records kept; aggregates: **confusion matrix, per-reciter top-1/3/5 + precision, score distributions for correct vs wrong predictions, top1–top2 margin stats, per-surah and per-clip-duration breakdowns, latency p50**. Output: timestamped JSON (machine-readable, includes every clip record) + Markdown report. A validation run on the full 20 reciters **reproduced 97.31% exactly**, so future experiments compare against a frozen protocol.

---

## 5. The 20 reciters

| key | reciter | source | key | reciter | source |
|---|---|---|---|---|---|
| abdulbaset | Abdulbaset Abdussamad | qa 37 | alafasy | Mishary Alafasy | qa 5 |
| minshawi | Mohamed Al-Minshawi | qa 6 | ghamdi | Saad Al-Ghamdi | qa 13 (`complete/`) |
| husary | Mahmoud Al-Hussary | qa 122 | ajmy | Ahmed Al-Ajmy | qa 19 |
| mustafa | Mustafa Ismail | qa 88 | qatami | Nasser Al-Qatami | qa 104 |
| banna | Mahmoud Ali Al-Banna | qa 129 | hani | Hani Ar-Rifai | qa 27 |
| sudais | Abdurrahman As-Sudais | qa 7 | abkar | Idris Abkar | mp3quran `abkr` |
| shuraim | Saud Al-Shuraim | qa 4 | fares | Fares Abbad | qa 14 |
| maher | Maher Al-Muaiqly | qa 159 (`year1440/`) | kurdi | Raad Al-Kurdi | qa 168 (`mp3/`) |
| juhany | Abdullah Al-Juhany | qa 1 | tunaiji | Khalifa Al-Tunaiji | qa 161 |
| dosari | Yasser Al-Dosari | qa 97 | ossi | Abdul Rahman Al-Ossi | mp3quran `aloosi` |

(qa = quranicaudio.com reciter id; slugs in parentheses include subfolders)

---

## 6. Problems discovered and how they were solved (the interesting part)

### 6.1 Environment breakage (torchaudio / huggingface_hub)
torchaudio ≥2.9 removed decoding backends (needs torchcodec; pinned torchcodec is incompatible with torch 2.14) → **switched audio loading to `soundfile`** with ffmpeg subprocess fallback. New `huggingface_hub` removed `use_auth_token`, breaking SpeechBrain's fetch → **pinned `huggingface_hub<0.26`**.

### 6.2 Silent dataset pollution (the most instructive failure)
Idris Abkar's quranicaudio archive (id 116) **contains multiple different voices across surahs**. Symptom: 2.6% eval accuracy while his *training* clips matched his profile at 0.78 cosine — the archive's other surahs simply weren't him. Diagnosis path: per-surah vote breakdown showed surah 36 = 226/227 self-matches, every other surah = other reciters. Fixes attempted:
- A clustering-based "dominant voice" profile filter → **made things worse** (fragmented legitimate profiles; abdulbaset 77.5→62.5%) → reverted.
- **Source swap** to mp3quran's dedicated `abkr` server → combined with 6.3, fixed completely (100%).

Lesson: **per-reciter, per-surah vote diagnostics are the right tool for archive pollution; automatic clustering of embeddings is not.**

### 6.3 Single-surah profile collapse
With clips sorted by filename, "first 80" = one surah. Abkar's profile built only from surah 36 scored his other archives' clips at ~0.42 (vs 0.78 for true surah-36 clips). **Round-robin sampling across surahs** took him from 0% → 100% (75/75 in the diagnostic, 38/38 in eval). Generalizes: profile diversity matters as much as profile size.

### 6.4 Serving-path defects (found by a skeptical audit)
- **C1: all inference blocked the event loop** — the async route called a ~1.3 s ECAPA pass (plus a blocking ffmpeg `subprocess.run`) directly; the entire server froze during identification. Fix: `anyio.to_thread.run_sync` around decode+identify, `Semaphore(2)` inference bound. Verified with a **heartbeat regression test**: a 5 ms ticker runs during a stubbed 1.5 s inference; pre-fix it got **0 ticks**, post-fix it passes. (A naive "time the health request" test was proven vacuous — the loop block also delays the test's own `asyncio.sleep`, silently shifting the measurement window. The heartbeat sidesteps that.)
- **C2: live webm streaming could never work** — only the first MediaRecorder chunk carries the webm header; per-chunk decoding failed for every later chunk. Fixed server-side with the dual-strategy decoder (§3), validated by streaming a real ffmpeg-generated webm split across 7 headerless chunks.
- **H1/H2: unbounded uploads** — size cap was checked after `await file.read()` buffered everything; and 25 MB of mp3 ≈ hours of audio = CPU DoS. Fixes: streamed 1 MiB capped reads; decoded audio trimmed to 30 s.

### 6.5 Naming consistency
Three name spaces existed (DB keys, clip dirs, display names). Verified programmatically that DB keys = clip dirs = `RECITERS` keys; `reciters.json` regenerated from the registry; API returns `{reciter: key, display: "Idris Abkar", score}` and the frontend prefers `display`.

---

## 7. Results

### 7.1 Final evaluation (781 held-out clips, surahs 78/87/93/112, never used for profiles)

| reciter | top-1 | reciter | top-1 |
|---|---|---|---|
| abdulbaset | 77.5% | ajmy | 100% |
| husary | 85.4% | alafasy | 100% |
| hani | 92.7% | banna | 100% |
| shuraim | 97.1% | fares | 100% |
| dosari | 97.3% | ghamdi | 100% |
| kurdi | 97.6% | juhany | 100% |
| abkar | 100% | maher | 100% |
| | | minshawi | 100% |
| | | mustafa | 100% |
| | | ossi | 100% |
| | | qatami | 100% |
| | | sudais | 100% |
| | | tunaiji | 100% |

**OVERALL top-1: 97.31% (760/781) · top-3: 99.10% · top-5: 99.62% · p50 latency ~1.34 s/clip (CPU)**

### 7.2 What the deep report adds
- **Errors are concentrated, not diffuse**: 21 errors, all inside 3 pairs — abdulbaset↔dosari/banna (8+1), husary→abdulbaset (6), hani→ossi (3), plus three singletons. 14 reciters have literally zero confusions.
- **abdulbaset's top-3 is 97.5%**: the right answer is almost always retrieved; top-1 *discrimination* between styles is the bottleneck — precisely the case multi-profile centroids target.
- **Score distributions overlap**: wrong predictions reach 0.636 cosine while the weakest correct prediction scores 0.238 → absolute-threshold unknown rejection (§10 #5) cannot be clean alone; needs threshold + margin.
- **Duration cost**: 5 s clips → 93.6% (−3.7 pts vs 10 s). The live mode's 5 s window operates in this lower regime.

### 7.3 Engineering quality gates (current)
ruff clean · pytest **23 passing** (audio decode incl. real webm/opus, API error contract, WS protocol, heartbeat concurrency regression, profile trim) · `tsc --noEmit` clean · Docker healthchecks · 4 commits, working tree clean.

---

## 8. Repository map

```
quranic-shazam/
├── backend/
│   ├── app/
│   │   ├── api/          routes (reciter.py, live_reciter.py), schemas.py
│   │   ├── core/         audio.py (soundfile+ffmpeg), embeddings.py (ECAPA singleton),
│   │   │                 similarity.py (cosine rank + display map), config.py (pydantic-settings)
│   │   ├── services/     reciter_service.py (profile DB, display names, semaphore)
│   │   └── main.py       app factory, lifespan (DB warm, optional model warm-up), CORS, /health
│   ├── scripts/          sources.py, generate_data.py, extract_embeddings.py,
│   │                     evaluate.py, evaluate_report.py
│   ├── data/             reciters.json, reciters_embeddings.npy, recitations_clips/ (19 GB, gitignored),
│   │                     eval_reports/ (JSON+MD)
│   ├── tests/            23 tests, no heavy model required
│   └── pyproject.toml    uv; torch CPU; huggingface_hub<0.26
├── frontend/             React+TS+Vite+Tailwind; api.ts, types.ts, hooks/useLiveReciter.ts
├── docker-compose.yml    backend :8000, frontend :8080
├── Makefile              data / embeddings / evaluate / dev / test / lint
├── PROJECT_DESIGN.md     earlier design doc
├── AUDIT.md              read-only architecture audit (C1/C2 findings)
└── PROJECT_REPORT.md     this document
```

**Key config** (env, `QD_` prefix): `QD_MAX_UPLOAD_MB=25`, `QD_MAX_AUDIO_SEC=30`, `QD_WARM_MODEL=0|1`, `QD_LIVE_WINDOW_SEC=5`, `QD_LIVE_MAX_DURATION_SEC=30`, `QD_LIVE_CONFIDENCE_THRESHOLD=0.85`, `QD_CORS_ORIGINS`.

---

## 9. Honest assessment

**Strong:** the offline pipeline (source resolution, resumable downloads, disjoint eval, round-robin profiles) · the frozen, reproducible 97.31% baseline with a real harness · clean layering · the debugging discipline (vote diagnostics, heartbeat test).

**Weak / honest caveats:**
- Most of the code was AI-assisted ("vibecoded") from v0 through v2; the audit-then-fix loop is what turned it into something defensible. Review depth is still thin in places (e.g. no integration test of the full Docker stack).
- Eval clips come from the same archives as training clips (same mastering/channel characteristics per reciter) — accuracy on *foreign* recordings (different mics, YouTube rips, phone recordings) is unmeasured and will be lower.
- 781 eval clips is small; per-reciter numbers have ±3–7 pt error bars.
- `pretrained_models/` (~80 MB) committed to git; eval audio re-downloaded each run (honest but fragile — archives rot).
- Closed-set only: the system always answers with one of the 20, however wrong.

---

## 10. Roadmap (agreed experiment order; every change must beat/compare against the frozen 97.31%)

1. ~~Architecture audit~~ ✅ (`AUDIT.md`)
2. ~~Fix inference architecture~~ ✅ (C1 + semaphore, heartbeat-verified)
3. ~~Deep evaluation framework~~ ✅ (`evaluate_report.py`)
4. **Multi-profile enrollment** ← next: k-means centroids (k=2..5, min cluster size floor) + max-similarity scoring; second arm: style-aware split (murattal/mujawwad) for abdulbaset; expected upside concentrated in the abdulbaset/dosari/husary triangle; keep single-mean default if not robustly better.
5. **Unknown-reciter rejection**: threshold + margin (absolute threshold provably insufficient — §7.2); needs out-of-distribution audio protocol.
6. **Data-quality diagnostics**: automated per-surah vote reports, cross-reciter near-duplicate detection — generalize the abkar discovery.
7. **Robustness suite**: noise, reverb, codecs, sample rates, phone-speaker playback, duration sweep → does 97.31% survive real users?
8. **Deployment hardening**: non-root containers, resource limits, structured logging/request IDs, ffmpeg timeout tests, frozen eval manifest with checksums.
9. **Tests**: keep growing by risk (inference-timeout, compose integration), not by line count.

*Rule: no "refactor everything" — the system is experimentally frozen at 97.31% and every change is measured against it.*
