# Quranic Shazam — Project Documentation & System Design

> "Shazam for Quran reciters": given a short audio clip of Quran recitation, identify which of 20 well-known reciters is speaking. Browser-based upload or live microphone recording, FastAPI backend, speaker-embedding matching (no model training).

---

## 1. Problem Statement & Approach

**Goal:** top-1 reciter identification from ~10 seconds of recitation audio, across 20 reciters, on CPU-only hardware.

**Approach:** speaker verification, not classification training.
- Use a pretrained speaker-embedding model (SpeechBrain ECAPA-TDNN, trained on VoxCeleb) as a fixed feature extractor. It outputs a 192-dim speaker embedding per clip.
- Build one **mean embedding profile per reciter** from ~80 training clips (10 s each, sampled round-robin across 4 training surahs).
- At query time: embed the query clip, compute **cosine similarity** against all 20 profiles, return ranked matches.

This is a "enrollment + nearest-profile" design (like voice-print systems), so adding a new reciter requires no retraining — just downloading clips and adding a profile.

**Final evaluation result: 97.31% overall top-1 accuracy (760/781 eval clips), 20 reciters, held-out surahs never used for profiles.**

---

## 2. High-Level Architecture

```
                        ┌────────────────────────────────────────────┐
                        │              DATA PIPELINE (offline)       │
                        │                                            │
  quranicaudio.com ──┐  │  scripts/sources.py     (URL resolution)   │
  surahquran.com  ───┤─▶│  scripts/generate_data.py (download+split) │
  (mp3quran CDN)      │ │  scripts/extract_embeddings.py             │
                      │ │      └─▶ data/reciters_embeddings.npy      │
                      │ │  scripts/evaluate.py (accuracy harness)    │
                      │ └────────────────────────────────────────────┘
                      │
Browser (React+TS)    ▼
┌──────────────┐  HTTP POST /identify_reciter (multipart audio)
│  Frontend    │─────────────────────────────▶ ┌──────────────────────────────┐
│  Vite dev /  │                              │  FastAPI backend             │
│  nginx dock  │◀─────────────────────────────│  app/api/routes/reciter.py   │
│              │  JSON {matches:[{reciter,    │    decode → embed → rank     │
└──────────────┘   display, score}]}           │  app/services/reciter_service│
┌──────────────┐  WebSocket /ws/live-reciter  │  app/core/embeddings.py      │
│  Live mic    │═════════════════════════════▶│  app/api/routes/live_reciter │
│  recording   │  streams wav chunks; server  │  (chunked identify, stops at │
└──────────────┘  replies when confident      │   confidence threshold)      │
                                             └──────────────────────────────┘
```

Deployment: `docker-compose.yml` — backend on :8000 (uvicorn), frontend on :8080 (nginx serving the Vite build). CPU-only PyTorch (whl/cpu index).

---

## 3. Backend Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI app assembly, CORS, routers
│   ├── api/
│   │   ├── schemas.py             # ReciterMatch{reciter, display, score}, IdentifyResponse, HealthResponse
│   │   └── routes/
│   │       ├── reciter.py         # POST /identify_reciter (file upload)
│   │       └── live_reciter.py    # WS /ws/live-reciter (streaming mic identification)
│   ├── core/
│   │   ├── config.py              # pydantic-settings: paths, top_k, live_confidence_threshold
│   │   ├── audio.py               # load/decode audio → 16 kHz mono float32 (soundfile + ffmpeg fallback)
│   │   ├── embeddings.py          # SpeechBrain EncoderClassifier singleton; embed waveform/file
│   │   └── similarity.py          # cosine similarity + rank_reciters (adds display names)
│   └── services/
│       └── reciter_service.py     # loads reciters_embeddings.npy once (thread-safe), identify_*
├── scripts/
│   ├── sources.py                 # ReciterSpec registry (20 reciters), URL resolution, downloaders
│   ├── generate_data.py           # downloads surahs, splits into 10 s clips (5 s overlap)
│   ├── extract_embeddings.py      # builds per-reciter mean profiles → reciters_embeddings.npy
│   └── evaluate.py                # held-out-surah accuracy harness
├── data/
│   ├── reciters.json              # 20 reciters: {name, key, id} (metadata, aligned with sources.py)
│   ├── reciters_embeddings.npy    # dict[key] → 192-dim mean profile (the "model DB")
│   └── recitations_clips/         # ~12,500 wav clips, <key>/<surah>_<n>.wav  (gitignored, ~14 GB)
├── pretrained_models/             # cached SpeechBrain ECAPA checkpoints
├── tests/                         # pytest: 3 tests (audio utils, similarity, API)
├── pyproject.toml                 # uv-managed deps; torch 2.14+cpu, speechbrain, huggingface_hub<0.26
├── Dockerfile, .env.example
```

### Request flow (upload identification)
1. `POST /identify_reciter` receives an audio file (mp3/wav/ogg/webm).
2. `audio.decode_upload_bytes` decodes it (soundfile fast path, ffmpeg subprocess fallback for webm/opus) to 16 kHz mono.
3. `embeddings.embedding_from_waveform` runs ECAPA-TDNN → 192-dim vector (~1 s CPU).
4. `similarity.rank_reciters` scores cosine similarity against the 20 loaded profiles, returns top-k with display names.

### Live mode (WebSocket)
Client records with MediaRecorder and streams binary chunks. Server accumulates audio, periodically embeds the buffer, and replies with matches; when top-1 score ≥ `live_confidence_threshold`, it tells the client to stop recording.

---

## 4. Data Pipeline

### Sources (`scripts/sources.py`)
- **Primary: quranicaudio.com** — `https://download.quranicaudio.com/quran/{slug}/{NNN}.mp3`. The slug (sometimes with subfolder, e.g. `maher_almu3aiqly/year1440/`) is scraped once from the reciter page (`quranicaudio.com/quran/{id}`) and cached as a template.
- **Fallback: surahquran.com** — page-scrapes the mp3 URL (hotlinks mp3quran.net / archive.org). Used for reciters absent from quranicaudio (Al-Ossi) or with polluted archives (Idris Abkar — his quranicaudio archive mixes other voices; swapped to `server6.mp3quran.net/abkr/`).
- Legacy islamic.network CDN support kept for the original 3-reciter version.
- Registry: `RECITERS: dict[key, ReciterSpec]` with `qa_id`, `sq_slug`, `cdn_code`, display name. This registry is the single source of truth for reciter identity/naming.

### Clip generation (`generate_data.py`)
- Downloads whole-surah MP3s per reciter, splits into **10 s clips with 5 s overlap** via pydub, saves wav per clip. Resume support (skips surahs already on disk). ThreadPool of 4.
- Training surahs: **36, 55, 56, 67** (medium length, bounded download).
- Eval surahs: **78, 87, 93, 112** — completely disjoint from training, so evaluation is honest.
- Dataset: 20 reciters × 8 surahs ≈ 12,500 clips, ~14 GB.

### Profile building (`extract_embeddings.py`)
- Per reciter: take up to **80 clips sampled round-robin across the training surahs** (important: taking "first 80 sorted" put all clips in one surah and collapsed one reciter's accuracy from 100% → 8%), embed each, **mean-pool** → one 192-dim profile.
- Output: `data/reciters_embeddings.npy` (dict of 20 profiles, ~20 KB).

### Evaluation (`evaluate.py`)
- Downloads eval surahs fresh, splits into clips (capped 12/surah), embeds each, ranks against the DB, reports per-reciter and overall top-1.

---

## 5. Reciters (20)

| key | display | source |
|---|---|---|
| abdulbaset | Abdulbaset Abdussamad | quranicaudio 37 |
| minshawi | Mohamed Al-Minshawi | quranicaudio 6 |
| husary | Mahmoud Al-Hussary | quranicaudio 122 |
| mustafa | Mustafa Ismail | quranicaudio 88 |
| banna | Mahmoud Ali Al-Banna | quranicaudio 129 |
| sudais | Abdurrahman As-Sudais | quranicaudio 7 |
| shuraim | Saud Al-Shuraim | quranicaudio 4 |
| maher | Maher Al-Muaiqly | quranicaudio 159 (`year1440/`) |
| juhany | Abdullah Al-Juhany | quranicaudio 1 |
| dosari | Yasser Al-Dosari | quranicaudio 97 |
| alafasy | Mishary Alafasy | quranicaudio 5 |
| ghamdi | Saad Al-Ghamdi | quranicaudio 13 (`complete/`) |
| ajmy | Ahmed Al-Ajmy | quranicaudio 19 |
| qatami | Nasser Al-Qatami | quranicaudio 104 |
| hani | Hani Ar-Rifai | quranicaudio 27 |
| abkar | Idris Abkar | surahquran → mp3quran `abkr` |
| fares | Fares Abbad | quranicaudio 14 |
| kurdi | Raad Al-Kurdi | quranicaudio 168 (`mp3/`) |
| tunaiji | Khalifa Al-Tunaiji | quranicaudio 161 |
| ossi | Abdul Rahman Al-Ossi | surahquran → mp3quran `aloosi` |

---

## 6. Evaluation Results (final)

Held-out surahs 78/87/93/112, 781 eval clips total:

```
abdulbaset  77.50%   minshawi  100%     husary     85.37%   mustafa  100%
banna       100%     sudais    100%     shuraim    97.14%   maher    100%
juhany      100%     dosari    97.30%   alafasy    100%     ghamdi   100%
ajmy        100%     qatami    100%     hani       92.68%   abkar    100%
fares       100%     kurdi     97.56%   tunaiji    100%     ossi     100%
OVERALL: 97.31% (760/781)
```

---

## 7. Frontend

React + TypeScript + Vite + Tailwind.
- `src/api.ts` — REST + WS clients; `src/types.ts` — `ReciterMatch {reciter, display?, score}`.
- `App.tsx`, `components/IdentificationForm` (file upload + audio player), `components/Result` (top match + ranked list, shows `display` names), `hooks/useLiveReciter.ts` (mic streaming via WebSocket).
- Dockerfile: node build → nginx serve on :8080.

---

## 8. Tooling & Conventions

- **uv** for Python deps (`pyproject.toml` + `uv.lock`), CPU-only torch wheel index. Pinned `huggingface_hub<0.26` (speechbrain passes the removed `use_auth_token` kwarg to newer versions).
- **make** targets at repo root: `make data`, `make embeddings`, `make evaluate` (wrap the scripts).
- ruff (lint, passing), pytest (3/3), `tsc --noEmit` (passing), Vite build (passing).
- WSL2 Ubuntu dev environment; repo at `/home/taha/quranic-shazam`; `.gitattributes` forces LF.

---

## 9. Key Design Decisions & Lessons (useful context for analysis)

1. **Embedding matching over training a classifier** — zero training, O(1) model, trivially extensible; cost is that profile quality depends on clip diversity.
2. **Round-robin clip sampling across surahs for profiles** — single-surah profiles overfit to that recitation's style/recording; this one change fixed a 100%→8% failure.
3. **Public audio archives can be polluted** — one reciter's archive contained whole surahs by different voices. Symptom: near-zero self-match with high similarity of *training* clips to *other* reciters. Mitigation: per-surah vote diagnostics + source swap. (A clustering-based auto-filter was tried and reverted: it fragmented legit profiles and hurt borderline reciters.)
4. **torchaudio ≥2.9 dropped decoding backends** — decode via soundfile; ffmpeg subprocess fallback for webm/opus uploads.
5. **Honest evaluation** — eval surahs are strictly disjoint from profile surahs; clips re-downloaded at eval time.
6. **Threshold-based live mode** — stream mic audio, stop when cosine confidence ≥ threshold (avoids forcing the user to record a fixed duration).

## 10. Known Limitations / Open Questions

- Single mean profile per reciter: reciters with strongly different styles (mujawwad vs murattal, e.g. Abdulbaset at 77.5%) would benefit from multiple style-specific profiles or per-clip voting.
- Cosine scores across ~20 profiles: no calibration; the live confidence threshold is hand-tuned.
- No anti-spoofing, no handling of unknown-reciter rejection (top-1 is always returned).
- Dataset balance varies per reciter (394–926 clips); profiles use only 80 clips each.
- Clips dataset (14 GB) not in git; pipeline must be re-run from source sites.
