# PickOne

Global rules (comments, TDD, verification, tone, git/plans workflow) live in `~/CLAUDE.md`. This file covers only
what's specific to PickOne.

## 1. Stack
<stack>
*   **Core:** Pairwise choice game — Next.js 15 (React 19, TS, Tailwind 4) frontend + FastAPI (Python 3.12, Pydantic v2) backend. PostgreSQL (SQLAlchemy 2.0 async + Alembic) is the ONLY datastore (no Elasticsearch, no Redis).
*   **Domain boundaries:** modules live under `backend/src/pickone/` (src-layout; the names below are import paths, not directories). `pickone.rating` is pure — no DB, no framework, no import of `pickone.battles` or `pickone.matchmaking`. `pickone.matchmaking` never imports `pickone.rating`. `pickone.public` holds no write path — no `pickone.battles`, no `pickone.moderation`. Enforced by `import-linter` contracts in `backend/pyproject.toml`, which are the authority. Never work around a contract.
*   **Correctness-first database:** Invariants (one pending battle per user, exactly-once rating application, ascending-lock-order transactions) live in Postgres constraints or locking transactions. Tests run against real Postgres — never mock the DB for transactions or constraints.
*   **Tooling:** `make` targets are the entry point (`make check`, `make test`, `make lint`); fall back to `curl`/`docker compose exec` only where no target exists. Add a target when you repeat a raw command.
*   **Local URLs:** Frontend: `http://localhost:3100` · Backend: `http://localhost:8100` · API docs: `/docs`.
</stack>

## 2. Rules
*   **Verification:** API-only checks → `curl`. Layout/theme rendering → screenshot. Rebuild Docker containers only
    when a `Dockerfile` or lockfile changes.
*   **Linting:** `make lint` is the whole check (`ruff check`, `ruff format`, `mypy` strict on `rating/` & `battles/`,
    `import-linter`, eslint, `tsc`).

## 3. Architecture
*   **Backend:** Pydantic v2 does not coerce UUID to `str` automatically — build response schemas explicitly, never rely on `from_attributes` for a UUID field. Postgres-backed fixed-window / `FOR UPDATE SKIP LOCKED` primitives for rate limiting and outbox delivery (no Redis until >4 API processes or p95 check latency >5ms).
*   **Frontend:** Tailwind 4 CSS-first tokens in `app/globals.css` on bare `:root` with dark/light overrides layered
    on top, never only inside a media query. `react/no-danger` is an ESLint error with zero exceptions — item text is
    user content rendered strictly as text, never HTML.

## 4. Gotchas
*   **SQLAlchemy 2.0+:** Async-only — no `session.query()`, no sync `Session`.
*   **Pydantic v2:** `.model_dump()`, `.model_dump_json()`, `@field_validator`. No automatic UUID → `str` coercion.
*   **Tailwind 4:** CSS-first config, no `tailwind.config.js`.
*   **Next.js 15 / React 19:** App Router only, `use()` for async data, `ref` is a plain prop.
*   **Alembic Autogenerate:** Pre-existing Postgres enums emit a bare `postgresql.ENUM(...)` that tries to `CREATE TYPE` again — add `create_type=False` by hand in generated migration.
*   **The `client` fixture and real commits:** a route that calls `session.commit()` (correct, matching production) writes permanently to the shared test database if `client` uses the app's own real session — the next test that expects an exact row count breaks, non-deterministically, based on test order. The `client` fixture must override `get_session` with the same per-test `db_session` used elsewhere, and that session needs `join_transaction_mode="create_savepoint"` so repeated internal `.commit()` calls release a savepoint instead of the fixture's outer transaction — the outer transaction (and everything written through it, including via `client`) still rolls back at teardown. Middleware that touches the database (e.g. CSRF) needs the same session injected separately, since it runs outside FastAPI's dependency-override system — `create_app()` takes an explicit `session_scope` for this.
*   **`@lru_cache`d engine/sessionmaker under pytest:** correct in production (one process, one long-lived loop) but wrong under pytest's per-test event loops — the cache survives across tests and a later test inherits a connection pool bound to an earlier test's dead loop ("Event loop is closed" at teardown, or a silent cross-loop `RuntimeError` on first query). An autouse fixture must clear and dispose `get_engine`/`get_sessionmaker`'s cache around every test that can reach them (including indirectly, e.g. through the app fixture) — clearing once at session scope is not enough.
*   **FastAPI + `from __future__ import annotations`:** a route function only resolves `Depends(x)` from `Annotated[T, Depends(x)]` if `x` is reachable via the route function's *module* globals at type-hint-evaluation time. Importing `x` inside an enclosing test-fixture function (a local, not a module global) makes FastAPI silently fall back to treating the parameter as a required query field — a 422 with no obvious cause. Always import anything referenced inside `Depends(...)` at module level, even in test files.
*   **pytest-asyncio:** `AsyncEngine` fixture must be function-scoped, not session-scoped (prevents connection binding to stale event loop across tests). `asyncio_default_fixture_loop_scope` must be `"function"` too — at `"session"`, a fixture that depends on another async fixture opening a real connection sets up on the session loop while the test body runs on a function loop, and the first query fails with "attached to a different loop" even though the fixture code is correct.

