# Quranic Shazam

A lightweight audio recognition project that identifies the reciter of a Quranic recitation by comparing embeddings against a precomputed library of known reciter voice profiles.

- FastAPI backend for audio upload and live recognition
- React + Vite + **TypeScript** frontend
- SpeechBrain embedding pipeline for speaker-style recognition
- Dataset generation and evaluation scripts
- `uv` for Python deps, `make` for backend tasks, Docker Compose for the full stack
- Developed/run inside **WSL Ubuntu** (see below)

---

## Project layout

```text
.
├── Makefile                 # all backend/frontend/docker tasks (run in WSL)
├── docker-compose.yml       # backend :8000 + frontend :8080
├── backend/
│   ├── pyproject.toml       # uv-managed Python deps (no requirements.txt)
│   ├── .python-version      # 3.10
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py          # create_app() factory, CORS, /health, routers
│   │   ├── api/routes/      # reciter.py (POST /identify_reciter), live_reciter.py (WS /live_reciter)
│   │   ├── api/schemas.py   # Pydantic response models
│   │   ├── core/            # config.py, audio.py, embeddings.py (lazy model), similarity.py
│   │   └── services/        # reciter_service.py (embeddings DB singleton + ranking)
│   ├── scripts/             # generate_data.py, extract_embeddings.py, evaluate.py (argparse CLIs)
│   ├── tests/               # pytest smoke tests (no heavy model needed)
│   └── data/                # reciters_embeddings.npy + clips (gitignored)
└── frontend/
    ├── vite.config.ts
    ├── tsconfig*.json
    ├── src/types.ts         # ReciterMatch / IdentifyResponse
    ├── src/api.ts           # API_BASE_URL + identifyReciter() (env-driven)
    ├── src/hooks/useLiveReciter.ts
    ├── src/components/IdentificationForm/IdentificationForm.tsx
    ├── src/components/Result/Result.tsx
    └── .env.example         # VITE_API_URL / VITE_WS_URL
```

API surface (unchanged for the frontend):

- `POST /identify_reciter?top_k=3` → `{ "matches": [{ "reciter", "score" }] }`
- `WS /live_reciter` → streams binary audio chunks, replies with `{ "matches": [...] }`
- `GET /health` → `{ "status": "ok", "reciters_loaded", "model_loaded" }`

---

## Run in WSL Ubuntu

The repo lives at `~/quranic-shazam` inside WSL (copied from Windows to avoid
`/mnt/c` performance issues). All commands below run in WSL:

```bash
cd ~/quranic-shazam
```

Prerequisites in WSL: `python3`, [`uv`](https://docs.astral.sh/uv/), `make`, `ffmpeg`, Node 20+.

```bash
uv --version && make --version && ffmpeg -version | head -n 1 && node --version
```

### Backend (uv + make)

```bash
make backend-install   # uv sync
make backend-test      # pytest smoke tests
make backend-dev       # uvicorn app.main:app --reload on :8000
```

Data pipeline:

```bash
make data              # download clips -> backend/data/recitations_clips
make embeddings        # mean embeddings -> backend/data/reciters_embeddings.npy
make evaluate          # accuracy on held-out clips
```

Config via env (`QD_` prefix, see `backend/.env.example`):
`QD_CORS_ORIGINS`, `QD_EMBEDDINGS_PATH`, `QD_MAX_UPLOAD_MB`,
`QD_LIVE_CONFIDENCE_THRESHOLD`, ...

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

## Notes on the refactor

- Backend: no import-time model load (lazy singleton in `app/core/embeddings.py`);
  uploads are decoded in-memory (`torchaudio` → `ffmpeg` fallback) instead of
  `temp_{filename}` files; embeddings DB loads once in `reciter_service`;
  shared cosine/ranking helpers in `app/core/similarity.py`; scripts are
  argparse CLIs with no import side effects.
- Frontend: `.jsx` → typed `.tsx`; API URLs come from `VITE_API_URL`/`VITE_WS_URL`;
  live-recording logic lives in `useLiveReciter`; `Result` renders all top-k matches.
- Old files removed: `backend/requirements.txt`, top-level `main.py` /
  `extract_embeddings.py` / `generate_data.py` / `identify_reciter.py` /
  `evaluate_accuracy.py`, `temp_*` audio junk, dead `AudioPlayer.jsx`.
