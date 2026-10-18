# syntax=docker/dockerfile:1
FROM python:3.10-slim AS runtime-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    HF_HOME=/app/.cache/huggingface \
    TORCH_HOME=/app/.cache/torch

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg libsndfile1 curl \
    && rm -rf /var/lib/apt/lists/*

# Keep native allocation peaks predictable on 512 MiB Linux instances.
ENV OPENBLAS_NUM_THREADS=2 \
    OMP_NUM_THREADS=2 \
    QD_INFERENCE_THREADS=2 \
    QD_LOW_MEMORY=true \
    MALLOC_ARENA_MAX=2 \
    MALLOC_MMAP_THRESHOLD_=131072 \
    MALLOC_TRIM_THRESHOLD_=131072

FROM runtime-base AS dependencies

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Dependency layer first for better caching
COPY pyproject.toml uv.lock .python-version README.md ./
RUN uv sync --frozen --no-dev --no-group export --no-install-project

# Serve the source directly; no editable project build or build tools in production.
FROM runtime-base AS serve

WORKDIR /app
COPY --from=dependencies /app/.venv /app/.venv
COPY app ./app
COPY scripts ./scripts
COPY data/reciters_embeddings.npy data/reciters.json data/quran_verses.json ./data/
# Fetch the versioned model asset; its checksum pins the exported weights.
COPY data/models/reciter.json ./data/models/
ARG RECITER_ONNX_URL=https://github.com/taha3313/quranic-shazam/releases/download/reciter-onnx-v1/reciter.onnx
RUN curl --fail --location --retry 5 --output data/models/reciter.onnx "$RECITER_ONNX_URL" \
    && echo "138051e261e072b080b97947ffe4ef21d6a99e496b4587c8b7a47de102d47552  data/models/reciter.onnx" \
        | sha256sum --check

# Bake the small Quran-tuned CTranslate2 ASR model into the image. Free Render
# instances lose their writable cache when they spin down, so downloading it on
# the first recognition request can add a large cold-start delay.
ARG ASR_MODEL_REVISION=8578bafd427d122f671b187706650e76edf6f86f
ENV QD_ASR_MODEL_SOURCE=/app/models/whisper
RUN .venv/bin/python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='OdyAsh/faster-whisper-base-ar-quran', revision='${ASR_MODEL_REVISION}', local_dir='/app/models/whisper', allow_patterns=['config.json','model.bin','preprocessor_config.json','vocabulary.json'])"

EXPOSE 8000

CMD ["sh", "-c", "exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8000}\""]
