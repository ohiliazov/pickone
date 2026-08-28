# Subpowers contract — PickOne

<!-- Read by the subpowers-* skills (plugin: subpowers@subpowers). Every command
     below is run verbatim.

     `make` is the canonical entry point — prefer a target over a raw
     docker/curl/psql invocation, and if you repeat a raw command, add a target
     instead of pasting it here. Raw equivalents are listed only where no target
     exists.

     Keep `## Project rules` in sync with CLAUDE.md — it is the single condensed copy. -->

## Commands

Run from the repo root. `make help` lists every target.

| Key | Command | Notes |
|-----|---------|-------|
| `test` | `make test` | Backend pytest against a **real** Postgres — never mock the DB for transactions or constraints |
| `test-one` | `cd backend && uv run pytest tests/path/test_file.py::test_name -v` | `make test` takes no args |
| `typecheck` | `cd backend && uv run mypy src tests` | Frontend: `cd frontend && npm run typecheck`. Both are inside `make lint` |
| `lint` | `make lint` | **The whole check** — `ruff check`, `ruff format --check`, `mypy src tests`, `lint-imports`, frontend `eslint` + `tsc`. Never invoke these piecemeal: that skips the import contracts and the frontend half |
| `build` | `cd frontend && npm run build` | **Load-bearing and not in `make lint`.** Only `make check` runs it |
| `check` | `make check` | `lint` + `test` + the frontend build. Everything CI runs — the bar for "ready for review" |
| `format` | `make format` | `ruff check --fix` + `ruff format` |
| `run` | `make up` | Postgres, API, worker, frontend |

Migrations: `make migration m="description"` then `make migrate` (`make downgrade` rolls back one).

## Inspect

Host ports come from `docker-compose.yml` and can move — read the live mapping
with `docker compose ps` rather than trusting a number cached anywhere.

```bash
# API — currently http://localhost:8100, interactive schema at /docs
curl localhost:8100/docs
curl localhost:8100/openapi.json | python3 -c 'import json,sys; print(*json.load(sys.stdin)["paths"], sep="\n")'

# Frontend — currently http://localhost:3100
curl localhost:3100/

# Postgres — read-only checks; schema changes go through `make migration` + `make migrate`
docker compose exec db psql -U pickone -d pickone -c "SELECT ..."

# Logs
docker compose logs -f [api|worker|web|db]

# No Redis and no Elasticsearch in this project — Postgres is the only datastore.
```

Compose stays running (bind mounts + hot reload) — only rebuild when a
`Dockerfile` or lockfile changes. API-only checks → `curl`, no browser;
layout/theme rendering → screenshot.

## Plans

- `dir:` `docs/subpowers/plans/`
- `archive:` `docs/subpowers/plans/archive/YYYY-MM-DD-<slug>/`

Repo-root `docs/`, not `backend/docs/`. Resolve it from the repo root, never
relative to the current directory.

## Evidence

| Claim | Required |
|-------|----------|
| "Tests pass" | `make test` output against real Postgres. A suite that mocked the DB proves nothing about a constraint or a locking transaction |
| "Import boundaries hold" | `lint-imports` clean inside `make lint` — reading the module tree is not evidence |
| "Frontend builds" | `cd frontend && npm run build`. `make lint` runs `tsc` but not the build; they fail on different things |
| "Ready for review" | `make check` green end to end |

## Project rules

Condensed copy of CLAUDE.md's laws — if a rule changes there, update this list.
`subpowers-implement`'s self-review applies it.

### Consistency

- [ ] Checked sibling components/pages for the same category of issue — not just the spot pointed at — before
      calling it done? A pattern that holds in one place holds everywhere it logically applies.
- [ ] No duplicated logic. One source of truth.

### Domain boundaries (enforced by `lint-imports`)

- [ ] `pickone.rating` stays pure — no database, no framework, no import of `pickone.battles` or `pickone.matchmaking`
- [ ] `pickone.matchmaking` never imports `pickone.rating`
- [ ] `pickone.public` holds no write path — no import of `pickone.battles` or `pickone.moderation`
- [ ] Never worked around a contract to make an import pass

### Backend

- [ ] Async SQLAlchemy only — no `session.query()`, no sync `Session`
- [ ] Pydantic v2: `.model_dump()`, `@field_validator`; UUID is **not** coerced to `str` automatically — build response
      schemas explicitly, never lean on `from_attributes` for a UUID field
- [ ] Invariants (one pending battle per user, exactly-once rating application, ascending lock order) live in Postgres
      constraints or locking transactions — not in application checks
- [ ] Rate limiting / outbox use Postgres fixed-window or `FOR UPDATE SKIP LOCKED` — no Redis until >4 API processes or
      p95 check latency >5ms
- [ ] New migration touching a pre-existing enum has `create_type=False` added by hand

### Frontend

- [ ] Mobile-first Tailwind (base, then `md:`/`lg:`)
- [ ] Tailwind 4 CSS-first tokens in `app/globals.css` on bare `:root`, with dark/light layered on top — never defined
      only inside a media query
- [ ] `react/no-danger` has zero exceptions — item text is user content, rendered strictly as text, never HTML

### Tooling

- [ ] Repeated a raw docker/curl/psql command? Add a `make` target and keep `make help` accurate

## Reindex / regeneration triggers

- Changed a model → `make migration m="description"` then `make migrate`
- Changed a domain module's imports → `make lint` re-runs `lint-imports`; a new boundary needs a contract in
  `backend/pyproject.toml`, not an exemption
