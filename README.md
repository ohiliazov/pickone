# PickOne

> PickOne lets you choose between anything, and everyone's choices create the world's ranking of everything.

The specification lives in [`docs/`](docs/). Start with [`docs/README.md`](docs/README.md).

**Current state: M0 complete.** A running skeleton — no product features yet.
Deployment to the Pi is wired end to end.

## Getting started

```bash
make install     # backend deps (uv) + frontend deps (npm)
make up          # Postgres + API + worker + frontend
```

- Frontend — http://localhost:3100
- API — http://localhost:8100 (`/healthz`, `/readyz`, `/docs`)
- Postgres — `localhost:5100`

PickOne owns the **3100 / 8100 / 5100** family rather than 3000 / 8000 / 5432,
which are the most contested ports on a machine running several stacks. If
even those collide, copy `.env.example` to `.env` and change
`PICKONE_WEB_PORT` / `PICKONE_API_PORT` / `PICKONE_DB_PORT`. Only the host
side moves; container ports never change.

```bash
make check       # everything CI runs: lint, types, boundaries, tests, build
make test        # backend suite against a real Postgres
make lint        # ruff + mypy + import-linter + eslint + tsc
```

## Layout

```
backend/            FastAPI, SQLAlchemy 2.0 async, Alembic
  src/pickone/
    core/           config register, clock, errors, logging
    db/             engine, session, base, migrations
    rating/         [M3] pure — imports no framework, no database
    matchmaking/    [M4] never imports rating/
    battles/        [M4] the only writer of ratings
    ...             one package per domain, created up front
    api/            routers, middleware
    worker/         scheduler + singleton lock
  tests/            real Postgres, never mocked
frontend/           Next.js 15 App Router, TypeScript, Tailwind v4
docs/               the specification and the milestone briefs
```

## The rules that outlive any milestone

Read [`docs/SPEC.md` §21.2](docs/SPEC.md#212-the-invariant-card) before changing
anything. The short version:

- Every actor has exactly one standing pending battle, enforced by a partial unique index.
- Ratings change only on `PENDING → COMPLETED`, exactly once per battle.
- `rating/` imports nothing from `db/` or any framework. `matchmaking/` never imports `rating/`.
- Items are locked in ascending id order in every multi-row transaction.
- `GET /api/battles/current` returns no rating, rank, deviation or count. Ever.
- No test that touches a transaction or a constraint may mock the database.
- Nothing goes between PICK and NEXT.

## Deployment

Production runs on a **Raspberry Pi**, behind a **Cloudflare Tunnel**. Nothing is
exposed to the internet: every container port binds to `127.0.0.1` and the only
route in is the tunnel.

```
                     Cloudflare
                          │  (tunnel — no inbound ports on the Pi)
                    ┌─────▼──────┐
                    │ cloudflared│  systemd, /etc/cloudflared/config.yml
                    └─────┬──────┘
        /api/* ───────────┼──────────────────────── everything else
              │           │                                │
      127.0.0.1:8100  (host)                        127.0.0.1:3100
              │                                             │
          ┌───▼───┐  ┌────────┐                         ┌───▼───┐
          │  api  │  │ worker │                          │  web  │
          └───┬───┘  └───┬────┘                          └───────┘
              └──────────┴──────────┐
                              ┌─────▼─────┐
                              │ postgres  │  (unpublished)
                              └───────────┘
```

Container logs, error tracking, and uptime monitoring are shared Pi-wide infra, not
part of this stack — see [`ohiliazov-pi`](https://github.com/ohiliazov/ohiliazov-pi).

### Sharing the Pi with other projects

The Pi already runs other stacks, so **every host-level artefact PickOne creates
is namespaced**, and `setup-pi.sh` aborts rather than overwrite anything it does
not recognise as its own:

| | PickOne uses | Would have collided with |
|---|---|---|
| Tunnel config | `/etc/cloudflared/pickone.yml` | `config.yml` — shared, owned by the first project |
| Tunnel service | `cloudflared-pickone.service` | `cloudflared.service`, via `cloudflared service install` |
| Runner directory | `~/actions-runner-pickone/` | `~/actions-runner/` — and its `DEPLOY_DIR` |
| Runner label | `pickone-prod` | `pi-prod` — a shared label deploys the wrong repo |
| Host ports | `8100` / `3100` | `8000` / `3000` |
| Image cleanup | only `ohiliazov/pickone-*` | host-wide `docker image prune -f` |
| Compose project | `pickone` (name, network, volumes) | — |

Two commands, both safe to run at any time:

```bash
bash scripts/pi/test-preflight.sh      # tests the guards; no Pi, Docker or root needed
bash scripts/pi/coexistence-check.sh   # read-only report of what PickOne owns on this Pi
```

Guards fail **closed**: if the setup cannot verify who owns something — an
unreadable runner registration, a config file without our marker — it stops
instead of assuming it is safe.

**One-time Pi setup** — idempotent, safe to re-run:

```bash
git clone git@github.com:ohiliazov/pickone.git && cd pickone
bash scripts/setup-pi.sh
cp .env.prod.example .env.prod && nano .env.prod
docker compose -f docker-compose.prod.yml up -d
```

`setup-pi.sh` installs Docker, installs cloudflared, creates and routes the
tunnel, and registers a `pi-prod` GitHub Actions runner.

**Releasing** — from your dev machine:

```bash
# bump VERSION, commit, push to main, then:
make push
```

`make push` refuses to run on a dirty tree, an unpushed commit, or an existing
tag; builds `linux/arm64,linux/amd64` images with buildx; pushes them to Docker
Hub; then pushes a `v<VERSION>` tag. The tag triggers
[`deploy.yml`](.github/workflows/deploy.yml) on the Pi runner, which pulls,
migrates, restarts, and then **verifies** — `/readyz`, the web root, and that
the worker actually took its singleton lock.

The Pi never builds. It pulls prebuilt multi-arch images.

Two things worth knowing before touching production:

- **`NEXT_PUBLIC_*` is baked in at image build time**, not read from `.env.prod`.
  `NEXT_PUBLIC_ENV=production` is what makes `robots.txt` allow crawling — build
  without it and the site ships `noindex` ([SPEC §14.8](docs/SPEC.md#148-robotstxt)).
- **Exactly one worker runs.** A Postgres advisory lock enforces it; a starting
  worker waits up to 30s for a departing one, then exits rather than doubling up.

## Configuration

Every `[CONFIG]` value in the spec is a named setting in
`backend/src/pickone/core/config.py` or `frontend/lib/config.ts`, loaded from the
environment and validated at boot. A magic number in a function body is a review
failure. See [`.env.example`](.env.example).
