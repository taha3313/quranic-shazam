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

ENV OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2

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
# Generate with the export dependency group before building this runtime image.
COPY data/models/reciter.onnx data/models/reciter.json ./data/models/

EXPOSE 8000

CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
