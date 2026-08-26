.DEFAULT_GOAL := help
SHELL := /bin/bash

# Host ports. PickOne owns the 3100/8100/5100 family so it does not fight
# the other stacks on this machine. Override in .env for docker compose.
WEB_PORT ?= 3100
API_PORT ?= 8100
DB_PORT  ?= 5100

BACKEND := backend
FRONTEND := frontend

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ------------------------------------------------------------------ setup
.PHONY: install
install: ## Install backend and frontend dependencies
	cd $(BACKEND) && uv sync --all-groups
	cd $(FRONTEND) && npm install

# ------------------------------------------------------------------ running
.PHONY: up
up: ## Start Postgres, API, worker and frontend
	docker compose up --build

.PHONY: down
down: ## Stop everything
	docker compose down

.PHONY: clean
clean: ## Stop everything and delete the database volume
	docker compose down -v

.PHONY: db
db: ## Start only Postgres (for running the API on the host)
	docker compose up -d db

.PHONY: api
api: ## Run the API on the host against the compose database
	cd $(BACKEND) && uv run uvicorn pickone.api.app:app --reload --port $(API_PORT)

.PHONY: worker
worker: ## Run the worker on the host
	cd $(BACKEND) && uv run pickone-worker

.PHONY: web
web: ## Run the frontend on the host
	cd $(FRONTEND) && npm run dev

# ------------------------------------------------------------------ database
.PHONY: migrate
migrate: ## Apply migrations
	cd $(BACKEND) && uv run alembic upgrade head

.PHONY: migration
migration: ## Create a migration: make migration m="add items"
	cd $(BACKEND) && uv run alembic revision --autogenerate -m "$(m)"

.PHONY: downgrade
downgrade: ## Roll back one migration
	cd $(BACKEND) && uv run alembic downgrade -1

# ------------------------------------------------------------------ checks
.PHONY: test
test: ## Run the backend test suite against a real Postgres
	cd $(BACKEND) && uv run pytest

.PHONY: lint
lint: ## Lint and typecheck everything
	cd $(BACKEND) && uv run ruff check . && uv run ruff format --check .
	cd $(BACKEND) && uv run mypy src tests
	cd $(BACKEND) && uv run lint-imports --config pyproject.toml
	cd $(FRONTEND) && npm run lint && npm run typecheck

.PHONY: format
format: ## Autoformat and autofix
	cd $(BACKEND) && uv run ruff check . --fix && uv run ruff format .

.PHONY: check
check: lint test ## Everything CI runs
	cd $(FRONTEND) && npm run build

# ------------------------------------------------------------------ release
# The Pi pulls prebuilt multi-arch images; it never builds. A Next.js build on
# a Pi is slow enough to be a bad idea, and buildx makes arm64 free from here.
REGISTRY   ?= ohiliazov
PUBLIC_URL ?= https://pickone.ohiliazov.com
VERSION    := $(shell cat VERSION)

.PHONY: push
push: ## Build multi-arch images, push them, then tag the release
	@if git rev-parse "v$(VERSION)" >/dev/null 2>&1 || \
	    git ls-remote --exit-code --tags origin "v$(VERSION)" >/dev/null 2>&1; then \
		echo "Tag v$(VERSION) already exists — bump VERSION first." >&2; exit 1; \
	fi
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "Working tree is dirty — commit and push to origin/main first." >&2; exit 1; \
	fi
	@git fetch origin main --quiet
	@if [ -n "$$(git log origin/main..HEAD)" ]; then \
		echo "Local main is ahead of origin/main — push first." >&2; exit 1; \
	fi
	docker buildx build --platform linux/arm64,linux/amd64 \
		--target runtime \
		--build-arg APP_VERSION=$(VERSION) \
		-t $(REGISTRY)/pickone-api:$(VERSION) -t $(REGISTRY)/pickone-api:latest \
		--push ./backend
	@# NEXT_PUBLIC_* are inlined at build time. NEXT_PUBLIC_ENV=production is
	@# what makes robots.txt allow crawling — omit it and the site ships noindex.
	docker buildx build --platform linux/arm64,linux/amd64 \
		--target runner \
		--build-arg NEXT_PUBLIC_ENV=production \
		--build-arg NEXT_PUBLIC_BASE_URL=$(PUBLIC_URL) \
		--build-arg NEXT_PUBLIC_API_URL=$(PUBLIC_URL) \
		-t $(REGISTRY)/pickone-web:$(VERSION) -t $(REGISTRY)/pickone-web:latest \
		--push ./frontend
	git tag v$(VERSION)
	git push origin v$(VERSION)

# ------------------------------------------------------------------ pi
.PHONY: prod-up
prod-up: ## (on the Pi) Start the production stack
	PICKONE_VERSION=$(VERSION) docker compose -f docker-compose.prod.yml up -d

.PHONY: prod-down
prod-down: ## (on the Pi) Stop the production stack
	docker compose -f docker-compose.prod.yml down

.PHONY: prod-logs
prod-logs: ## (on the Pi) Tail production logs
	docker compose -f docker-compose.prod.yml logs -f --tail 100

.PHONY: prod-ps
prod-ps: ## (on the Pi) Show production container state
	docker compose -f docker-compose.prod.yml ps -a
