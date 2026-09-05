.PHONY: help backend-install backend-dev backend-run backend-test backend-lint \
	data embeddings evaluate \
	frontend-install frontend-dev frontend-build frontend-preview frontend-typecheck \
	docker-build docker-up docker-down docker-logs

HOST ?= 0.0.0.0
PORT ?= 8000

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS=":.*?## "} {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------------- Backend (uv) ----------------

backend-install: ## Install backend deps with uv
	cd backend && uv sync

backend-dev: ## Run backend API in dev mode (reload)
	cd backend && uv run uvicorn app.main:app --reload --host $(HOST) --port $(PORT)

backend-run: ## Run backend API (production, no reload)
	cd backend && uv run uvicorn app.main:app --host $(HOST) --port $(PORT) --workers 1

backend-test: ## Run backend tests (no heavy model needed)
	cd backend && uv run pytest -q

backend-lint: ## Lint backend with ruff
	cd backend && uv run ruff check app scripts tests

# ---------------- Data pipeline ----------------

data: ## Download + split recitation clips
	cd backend && uv run python -m scripts.generate_data

embeddings: ## Compute reciter embeddings from clips
	cd backend && uv run python -m scripts.extract_embeddings

evaluate: ## Evaluate accuracy on held-out clips
	cd backend && uv run python -m scripts.evaluate

# ---------------- Frontend ----------------

frontend-install: ## Install frontend deps
	cd frontend && npm ci

frontend-dev: ## Run frontend dev server (Vite)
	cd frontend && npm run dev

frontend-build: ## Typecheck + build frontend
	cd frontend && npm run build

frontend-preview: ## Preview production frontend build
	cd frontend && npm run preview

frontend-typecheck: ## Typecheck frontend only
	cd frontend && npm run typecheck

# ---------------- Docker ----------------

docker-build: ## Build backend + frontend images
	docker compose build

docker-up: ## Start full stack (backend :8000, frontend :8080)
	docker compose up --build

docker-down: ## Stop full stack
	docker compose down

docker-logs: ## Tail stack logs
	docker compose logs -f
