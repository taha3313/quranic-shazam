# Quranic Shazam

Identify the reciter of a Quranic recitation from a short audio clip — upload a file or record live in the browser. Matches are made against precomputed voice-print profiles of **20 well-known reciters**.

**Measured accuracy: 97.3% top-1 (99.1% top-3) across 20 reciters on held-out surahs** — using a pretrained speaker-embedding model, with no training on Quran data.

- FastAPI backend: file upload + live WebSocket recognition
- React + Vite + **TypeScript** frontend
- SpeechBrain **ECAPA-TDNN** (VoxCeleb) speaker embeddings; per-reciter mean voice prints + cosine matching
- Reproducible dataset pipeline (quranicaudio.com / surahquran.com) and deep evaluation harness
- `uv` for Python deps, `make` for tasks, Docker Compose for the full stack
- Developed/run inside **WSL Ubuntu** (see below)

## How it works

1. **Profiles (offline):** ~80 ten-second clips per reciter (sampled round-robin across the training surahs 36/55/56/67) are embedded with ECAPA-TDNN and mean-pooled into one 192-dim voice print per reciter → `data/reciters_embeddings.npy`.
2. **Identification (online):** the query clip is decoded to 16 kHz mono, trimmed to 30 s, embedded, and ranked by cosine similarity against all profiles. Matches return `{reciter, display, score}`.
3. **Live mode:** the browser streams MediaRecorder audio over a WebSocket; the server decodes cumulatively, identifies over a sliding 5 s window, and answers as soon as the top-1 confidence (0.85 default) is reached.

Adding a reciter = add a `ReciterSpec` to `backend/scripts/sources.py`, download clips, rebuild profiles. No retraining.

## The 20 reciters

Abdul Basit · Minshawi · Husary · Mustafa Ismail · Al-Banna · Sudais · Shuraim · Maher Al-Muaiqly · Al-Juhany · Al-Dosari · Alafasy · Al-Ghamdi · Al-Ajmy · Nasser Al-Qatami · Hani Ar-Rifai · Idris Abkar · Fares Abbad · Raad Al-Kurdi · Khalifa Al-Tunaiji · Abdul Rahman Al-Ossi

## Project layout

```text
.
├── Makefile                 # all backend/frontend/docker tasks
├── docker-compose.yml       # backend :8000 + frontend :8080
├── backend/
│   ├── pyproject.toml       # uv-managed Python deps
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py          # app factory, CORS, /health, lifespan warm-up
│   │   ├── api/routes/      # reciter.py (POST /identify_reciter), live_reciter.py (WS /live_reciter)
│   │   ├── api/schemas.py   # Pydantic response models
│   │   ├── core/            # config.py, audio.py (soundfile + ffmpeg fallback),
│   │   │                    # embeddings.py (lazy ECAPA singleton), similarity.py
│   │   └── services/        # reciter_service.py (profile DB + bounded inference)
│   ├── scripts/             # sources.py, generate_data.py, extract_embeddings.py,
│   │                        # evaluate.py, evaluate_report.py (deep reports)
│   ├── tests/               # 23 pytest tests (no heavy model needed)
│   └── data/                # reciters.json, reciters_embeddings.npy,
│                            # recitations_clips/ (gitignored), eval_reports/
└── frontend/
    ├── src/types.ts         # ReciterMatch {reciter, display, score} / IdentifyResponse
    ├── src/api.ts           # API_BASE_URL + identifyReciter() (env-driven)
    ├── src/hooks/useLiveReciter.ts
    └── src/components/      # IdentificationForm.tsx, Result.tsx
```

## API

- `POST /identify_reciter?top_k=3` (multipart audio ≤ 25 MB) → `{ "matches": [{ "reciter", "display", "score" }] }`
- `POST /identify_verse?top_k=3&include_transcript=false` (multipart audio ≤ 25 MB, first 20 s used) → `{ "transcript?", "confident", "matches": [{ "surah", "surah_name", "ayah_start", "ayah_end", "score", "words_matched", "words_total", "text" }] }` — Quranic Whisper ASR (tarteel whisper-base-ar-quran, CT2 int8) + normalized fuzzy matching over the 6,236-verse corpus (Imla'i text, alquran.cloud/Tanzil); supports partial verses and jointly ranked ayah ranges; ambiguous locations return confident=false
- `POST /identify_verse_progressive` — accumulate context in ASR windows of at most 20 seconds, stop at a clear match or 60 seconds; returns `needs_more_audio`, `listen_limit_reached`, and `audio_seconds`. Microphone verse recognition checks automatically and keeps listening while uncertain.
- `WS /live_reciter` — stream binary audio chunks; replies `{ "matches": [...] }` on confidence, or `"Not sure"` after 30 s
- `GET /health` → `{ "status", "reciters_loaded", "model_loaded" }`

Verse-identification setup (one-time): `cd backend && uv run python scripts/build_verse_corpus.py` (regenerates `data/quran_verses.json`). The ASR model (~145 MB) downloads automatically on first `/identify_verse` call. See [docs/AYAH_ID_RESEARCH.md](docs/AYAH_ID_RESEARCH.md) for the model/retrieval investigation behind this feature.

---

## Run in WSL Ubuntu

The repo lives at `~/quranic-shazam` inside WSL. Prerequisites: `python3`, [`uv`](https://docs.astral.sh/uv/), `make`, `ffmpeg`, Node 20+.

```bash
cd ~/quranic-shazam
uv --version && make --version && ffmpeg -version | head -n 1 && node --version
```

### Backend (uv + make)

```bash
make backend-install   # uv sync
make backend-test      # pytest (23 tests, no heavy model)
make backend-dev       # uvicorn app.main:app --reload on :8000
```

Dataset pipeline (downloads ~19 GB of clips; resumable):

```bash
make data              # download + split clips -> backend/data/recitations_clips
make embeddings        # build voice prints -> backend/data/reciters_embeddings.npy
make evaluate          # top-1 accuracy on held-out surahs (78/87/93/112)
```

Deep evaluation (confusion matrix, top-k, score margins, per-surah/per-duration, JSON + Markdown):

```bash
cd backend && uv run python -m scripts.evaluate_report
```

Config via env (`QD_` prefix, see `backend/.env.example`): `QD_CORS_ORIGINS`,
`QD_MAX_UPLOAD_MB=25`, `QD_MAX_AUDIO_SEC=30`, `QD_WARM_MODEL`,
`QD_LIVE_WINDOW_SEC=5`, `QD_LIVE_MAX_DURATION_SEC=30`,
`QD_LIVE_CONFIDENCE_THRESHOLD=0.85`, `QD_EMBEDDINGS_PATH`, ...

### Frontend (TypeScript)

```bash
make frontend-install
make frontend-dev      # Vite on :5173
make frontend-build    # tsc -b && vite build
```

Configure the backend URL with `frontend/.env`:

```bash
cp frontend/.env.example frontend/.env
# VITE_API_URL=http://127.0.0.1:8000
```

### Docker Compose (optional)

Needs Docker Desktop with WSL integration enabled for the Ubuntu distro.

```bash
make docker-up     # backend :8000, frontend :8080
make docker-logs
make docker-down
```

---

## Evaluation results

Held-out surahs (78, 87, 93, 112 — never used for profiles), 781 clips:

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

**Overall: 97.31% top-1 · 99.10% top-3 · 99.62% top-5** · p50 latency ≈ 1.3 s per clip (CPU).

Full details: `PROJECT_REPORT.md` (architecture, data engineering, lessons, roadmap) and `AUDIT.md` (architecture audit). Machine-readable reports land in `backend/data/eval_reports/`.

## Notes on the implementation

- Lazy model singleton (`app/core/embeddings.py`), optional `QD_WARM_MODEL=1` startup warm-up; uploads decoded in memory via soundfile with an ffmpeg fallback for webm/opus; profile DB loaded once with display names from `data/reciters.json`.
- Inference runs in worker threads with a bounded semaphore, so health checks and concurrent sessions stay responsive during identification.
- Uploads are streamed and capped (`QD_MAX_UPLOAD_MB`); decoded audio trimmed to `QD_MAX_AUDIO_SEC`.
- Live WebSocket supports both self-contained chunks (wav) and container streams (webm/opus via cumulative decoding).
- Evaluation is honest: profile surahs (36/55/56/67) and eval surahs (78/87/93/112) are strictly disjoint, and eval audio is re-downloaded fresh at evaluation time.
