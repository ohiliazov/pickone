# M0 — Foundations & scaffolding

**Size:** S · **Depends on:** nothing · **Blocks:** everything
**Spec reference:** [§7.5](../SPEC.md#75-migrations), [§17](../SPEC.md#17-technical-architecture), [§21.3](../SPEC.md#213-the-configuration-register)

## Goal

A running, empty, correct skeleton: one command brings up Postgres, the API, the worker and the frontend locally; CI runs lint, types, migrations and tests on every commit. No product features.

## Scope

- Monorepo: `backend/` (Python 3.12, `uv` or Poetry), `frontend/` (Next.js 15 + TS + Tailwind), `docs/`, `docker-compose.yml`, `Makefile`.
- Backend package skeleton with the module boundaries from [§17.3](../SPEC.md#173-module-boundaries-backend) — empty packages with `__init__.py` and a one-line docstring each. Create them all now so nobody has to decide where code goes later.
- `pickone/core/config.py`: the configuration register. Pydantic `BaseSettings`, env-loaded, validated at boot, `ENV ∈ {local, test, preview, production}`. Seed it with the keys M0 needs (`DATABASE_URL`, `ENV`, `SECRET_KEY`, `BASE_URL`, `LOG_LEVEL`) and the structure for the rest.
- `pickone/core/errors.py`: the error envelope from [§8.1](../SPEC.md#81-conventions) plus a `PickOneError` hierarchy and a FastAPI exception handler that renders it.
- `pickone/core/clock.py`: an injectable clock (`now() -> datetime`). Every timestamp in the system goes through it — this is what makes expiry testable without `sleep`.
- `pickone/core/logging.py`: `structlog` JSON, `request_id` middleware.
- `db/`: async engine, session dependency, declarative base, Alembic wired to the ORM metadata.
- Health endpoints: `GET /healthz` (liveness, no DB) and `GET /readyz` (checks DB).
- Worker skeleton: a process that takes the singleton advisory lock ([§17.4](../SPEC.md#174-deployment)), starts APScheduler with zero jobs, and exits cleanly on a second instance.
- Frontend skeleton: App Router, Tailwind with the design tokens (colour, spacing, type scale, motion easings from [§5.3](../SPEC.md#53-animation-principles)), light + dark themes, a layout with the [§5.5](../SPEC.md#55-navigation) nav shell, and placeholder routes for `/`, `/rankings`, `/item/[slug]`, `/compare/[slug]`, `/play`, `/add`.
- Test harness: `pytest`, `pytest-asyncio`, testcontainers-backed Postgres fixture, a `db_session` fixture that rolls back, and a `client` fixture. **The Postgres fixture is the single most important thing in this milestone** — every later milestone depends on real-database tests being frictionless.
- CI (GitHub Actions): `ruff`, `mypy`, `eslint`, `tsc`, `pytest`, migrations-from-empty, autogenerate-diff-is-empty.
- `docs/DECISIONS.md` with the frontend fork decision from [§17.2](../SPEC.md#172-the-frontend-decision-honestly) recorded.

## Database changes

Alembic initialised. One migration creating the four enums from [§7.1](../SPEC.md#71-enums). No tables.

## API changes

`GET /healthz`, `GET /readyz`. Error-envelope handler. Request-id middleware.

## Frontend changes

Skeleton, tokens, themes, nav shell, placeholder routes rendering static text.

## Tests

- `test_healthz` / `test_readyz` (readyz fails when the DB is unreachable).
- `test_error_envelope_shape` — a raised `PickOneError` renders the documented JSON.
- `test_config_rejects_null_provider_in_production` — placeholder now, real in M2; the mechanism (env-conditional validation) is built here.
- `test_migrations_from_empty` and `test_no_autogenerate_diff`.
- `test_clock_is_injectable` — a fake clock changes `now()`.
- `test_worker_singleton` — a second worker instance exits non-zero without running jobs.
- Frontend: one render smoke test per placeholder route; a11y scan of the layout shell.

## Acceptance criteria

1. `make up` starts Postgres, API, worker and frontend; `curl localhost:8000/readyz` returns 200.
2. `make test` passes, and the Postgres-backed fixture spins up in under 10s on a cold cache.
3. CI is green on an empty PR and fails if a stray `print()` or an untyped function is added to `rating/` or `battles/`.
4. `ENV=production` with a missing required setting fails at **boot**, not on first request.
5. Every module directory from §17.3 exists.
6. Light and dark themes both render the nav shell correctly; `prefers-color-scheme` is respected.
7. `docs/DECISIONS.md` records the frontend choice with its rationale.

## Non-goals

No users, items, battles, ratings, moderation, real pages, real styling of the game screen, deployment to any environment, CDN, Sentry, or metrics endpoint. Auth middleware is not written here.
