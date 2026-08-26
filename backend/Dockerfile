# syntax=docker/dockerfile:1

# ── Dependency installer ──────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS deps

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# Prod deps first, so a source change does not reinstall the world.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY alembic.ini ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# VERSION lives at the repo root, outside this build context (./backend), so it
# arrives as a build arg rather than a COPY.
ARG APP_VERSION=0.0.0-dev
RUN echo "$APP_VERSION" > VERSION

# ── Development ───────────────────────────────────────────────────────────────
FROM deps AS development

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv

EXPOSE 8000
CMD ["uvicorn", "pickone.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Runtime ───────────────────────────────────────────────────────────────────
# Plain Python: no uv binary in the deployed image, and nothing from the dev group.
FROM python:3.12-slim AS runtime

WORKDIR /app

# The Pi runs this unattended for months. Nothing here needs root.
RUN groupadd --system pickone && useradd --system --gid pickone --home /app pickone

COPY --from=deps /opt/venv /opt/venv
COPY --from=deps /app/src ./src
COPY --from=deps /app/alembic.ini ./
COPY --from=deps /app/VERSION ./

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER pickone

EXPOSE 8000
CMD ["uvicorn", "pickone.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
