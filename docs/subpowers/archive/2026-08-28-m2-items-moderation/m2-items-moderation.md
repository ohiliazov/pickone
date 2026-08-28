---
status: complete
current_task: null
next_task: null
blocker: null
suite_expected: green
deps: []
updated: 2026-08-28
---

# M2 — Items & moderation — Implementation Plan

**Goal:** A verified user can add a plain-text item that is normalised, deduplicated, slugged, moderated, and either published at rating 0 or held for review, with a full admin surface and creation rate limits.

**Architecture:**
Two new pure-ish domains, `items/` and `moderation/`, following the exact layering already established by `auth/` in M1: `models.py` (ORM) → `repository.py` (CRUD, no business logic) → `service.py` (orchestration, transactions) → consumed by FastAPI routers in `api/routers/`. `items/service.create_item` owns the single creation transaction: it flushes the `Item` row first (so it has a real id), then calls `moderation.service.moderate()` to run the provider+policy pipeline and write the `moderation_results` row against that id, then updates the item's status — a `RejectedError` raise after that point relies on `get_session`'s existing rollback-on-exception behavior (already true today) to guarantee a rejected item is never committed. The admin surface is **JSON-only** at `/api/admin/*` (matches §8.5 literally); the admin screens themselves are ordinary Next.js pages under `app/admin/*` that call that same JSON API through the existing `apiFetch`/`AuthProvider` stack — no second rendering stack, no duplicated query/decision logic.

**Tech Stack:** Same as M1 (FastAPI/SQLAlchemy 2.0 async/Pydantic v2/Postgres + Next.js/React/Tailwind). No new dependencies.

**Decisions locked in from the pre-plan discussion:**
- Admin: JSON API at `/api/admin/*` only. The "separate HTML pages" are ordinary Next.js pages under `app/admin/*` consuming that same JSON API — the frontend already has the full cookie-session + CSRF + `apiFetch` stack built in M1, so a second server-rendered (Jinja) surface would only duplicate it for no reason. No new backend dependency.
- `GET /api/items/{slug}`: reduced schema in M2 — `rivals`/`biggest_wins`/`recent` fields are simply absent (not null placeholders); `rank` is always `null` and `ranked` always `false` until M3 (rating) and M4 (battles) exist.
- `/me`'s `items_remaining_today` gets fixed in this milestone (Task 21) to read the real rate-limit counter instead of the hardcoded M1 placeholder.
- Circuit breaker state is in-process/module-level (mirrors `core/clock.py`'s global pattern) — correct because production runs exactly one API process (`uvicorn` with no `--workers`), same reasoning as the existing "no Redis until >4 API processes" rule.
- The hard blocklist pre-filter (§12.1, §12.4 invariant) uses a small, honestly-named "starter" list (mirrors `starter_common_passwords.py` from M1) — a real production corpus is an ops concern, not something fabricated here.

---

### Task 1: Config — items & moderation settings [sequential]

**Satisfies:** Foundation for all rate limits, moderation config, acceptance criterion 5 (`ENV=production` + `NullProvider` fails at boot).

**Files:** Modify `backend/src/pickone/core/config.py`

- [x] Test: `cd backend && uv run pytest tests/test_config.py -k moderation_provider -x` → expect FAIL (test file/cases don't exist yet)
- [x] Add settings: `item_max_length=64`, `rl_items_per_hour_user=5`, `rl_items_per_day_user` (already exists, reuse=20), `rl_items_per_day_ip=50`, `rl_items_per_day_new_account=5`, `new_account_age_hours=24`, `moderation_provider: str = "heuristic"`, `openai_api_key: str = ""`, `moderation_model: str = "omni-moderation-latest"`, `moderation_timeout_ms=2500`, `moderation_policy_version: str = "v1"`, `moderation_circuit_breaker_threshold=10`, `moderation_circuit_breaker_cooldown_seconds=60.0`, `auto_hide_report_count=5`
- [x] Null-provider-in-production folded into the existing `_production_requires_real_values` validator (per `test_production_validator_is_the_seam_m2_will_reuse`'s intent); openai-key requirement added as its own `_openai_requires_a_key_in_production` validator, mirroring `_resend_requires_a_key_in_production`
- [x] Verify: `cd backend && uv run pytest tests/test_config.py -x` → PASS (14 tests), ruff/mypy clean

---

### Task 2: DB migration — items, moderation_results, item_reports [sequential]

**Satisfies:** §7.2/§7.3 tables, acceptance criteria 1 and 9 (`items_text_len_ck`, rating=0/rd=350 defaults).

**Files:** Create `backend/src/pickone/items/models.py`, `backend/src/pickone/moderation/models.py`, Modify `backend/src/pickone/db/all_models.py`, Create `backend/src/pickone/db/migrations/versions/0003_m2_items.py`

- [x] Test: `cd backend && uv run pytest tests/test_migrations.py -x` → FAIL as expected (missing 3 tables)
- [x] `Item` ORM model — added config-driven `rating`/`rating_deviation` server defaults (0.0000/350.0000) matching `item_default_rating`/`item_default_rating_deviation` added to Task 1's config; hit and fixed a real bug: the column named `text` (Item.text) shadows the module-level `text` import inside the class body, so `sqlalchemy.text` had to be imported as `sql_text` to avoid colliding with the ORM's own `text` attribute
- [x] `ModerationResult` and `ItemReport` ORM models, no cross-imports
- [x] Wired into `db/all_models.py`; emptied the two stub `__init__.py` docstrings
- [x] Autogenerated, renamed to `0003_m2_items.py`, hand-fixed both enums to `create_type=False`, added `server_default` for rating/rating_deviation to match config, stripped autogenerate comments and reformatted
- [x] Updated `tests/test_migrations.py`'s expected table set
- [x] Verify: PASS (19 tests), `alembic check` reports no diff, ruff/mypy clean

---

### Task 3: `items/normalize.py` — pure normalisation [independent]

**Satisfies:** §12.2, acceptance criterion 1 (no code path treats a normalised item as unvalidated).

**Files:** Create `backend/src/pickone/items/normalize.py`, `backend/tests/test_items_normalize.py`

- [x] Test: wrote 20 table-driven cases first (whitespace runs, zero-width/bidi ranges built from explicit codepoints — not literal invisible characters, verified via an `ast`-walk script since typing them directly is exactly the kind of mistake this function exists to catch — combining marks, casefold, emoji, mixed Cyrillic/Latin, C0 control rejection, idempotence) → FAIL (module didn't exist)
- [x] Implemented `display_text`/`normalized_text`. Decided `display_text` does NOT raise for C0/C1 controls being *stripped* — it raises `ControlCharacterError` (a local, dependency-free exception) only if a control character *remains* after zero-width/bidi stripping, matching §12.2's literal pseudocode; Task 5's validation will catch this
- [x] Verify: PASS (20 tests), ruff/mypy clean, source is pure ASCII (regex ranges built via `chr()`, not embedded invisible characters, so the file itself stays auditable)

---

### Task 4: `items/slugs.py` — pure slug generation [independent]

**Satisfies:** §14.3, acceptance criterion 7 (race-safety is Task 8's job; this task is the pure function).

**Files:** Create `backend/src/pickone/items/slugs.py`, `backend/tests/test_items_slugs.py`

- [x] Test: wrote first → FAIL (module didn't exist)
- [x] Implemented `slugify`: NFKD-strip-combining for ASCII transliteration, lowercase, hyphenate, `-vs-`→`-versus-` substitution done *before* truncation (so truncation can never reintroduce it and the 64-char cap is never violated by the substitution growing the string), then truncate at a word boundary
- [x] Found and fixed a real bug via the boundary test: `_truncate_at_word_boundary` unconditionally backed up to the previous hyphen whenever *any* hyphen existed in the truncated slice — even when the cut already landed cleanly on a boundary — silently dropping a whole extra word for no reason. Fixed by checking whether the character immediately after the cut point is itself a hyphen before backing up.
- [x] Property-style test (no hypothesis dependency in this repo, so a deliberate combinatorial sweep instead): every 2/3/4-length permutation of a 10-word pool including `vs`/`versus` — `-vs-` never survives in the output
- [x] Verify: PASS (14 tests), ruff/mypy clean

---

### Task 5: `items/validation.py` — structural validation [sequential]

**Satisfies:** §12.3, acceptance criterion 9 (DB-level check mirrored at the app level).

**Files:** Create `backend/src/pickone/items/errors.py`, `backend/src/pickone/items/validation.py`, `backend/tests/test_items_validation.py`

- [x] Test: 23 cases written first → FAIL (modules didn't exist)
- [x] `items/errors.py`: `InvalidTextError`, `RejectedError` (`__init__` takes no arguments at all — hard-blocks any call site from ever attaching `details`, guaranteeing criterion 4's "no category or score" leak-proofing at the type level, not just by convention), `AlreadyExistsError`
- [x] `items/validation.py`: `RESERVED_SLUGS`, `validate_structure`. Reserved-slug check compares against *both* the raw lowercased/stripped input and `slugify(display)` — caught a real gap where `slugify("_next")` returns `"next"` (slugify strips the underscore as non-alphanumeric), so checking only the slugified form would let literal `"_next"` input through unrejected even though it's explicitly in the reserved list
- [x] Verify: PASS (23 tests) — also had to retune one test's fixture: `"12345678"` looked like a pure majority-digits case but is also an 8-digit run that legitimately matches the phone-number pattern checked earlier in the same function, so the two rules were fighting over which fires first on the same input; replaced with `"12, 34"`, which is unambiguously digits+punctuation only. Ruff/mypy clean.

---

### Task 6: `moderation/starter_blocklist.py` + `moderation/policy.py` [independent]

**Satisfies:** §12.1 (hard blocklist pre-filter invariant), §12.5 (policy table + versioning).

**Files:** Create `backend/src/pickone/moderation/starter_blocklist.py`, `backend/src/pickone/moderation/policy.py`, `backend/tests/test_moderation_policy.py`

- [x] Test: 36 cases written first → FAIL (modules didn't exist)
- [x] `starter_blocklist.py`: `STARTER_BLOCKLIST` frozenset with two real, safe-to-write self-harm-incitement phrases ("kill yourself", "kys") — deliberately not slurs; a production corpus is an ops concern, not something fabricated here
- [x] `policy.py`: `Policy` as a `TypedDict` (not a loose `dict`, avoids an `assert isinstance` mypy-narrowing hack), `POLICY_V1` verbatim from §12.5, `decide()`
- [x] Verify: PASS (36 tests, every threshold boundary on both sides for every category), ruff/mypy clean

---

### Task 7: `moderation/provider.py` — provider protocol + 3 implementations [sequential]

**Satisfies:** §12.4, acceptance criterion 5.

**Files:** Create `backend/src/pickone/moderation/provider.py`, `backend/tests/test_moderation_provider.py`

- [x] Test: 7 cases written first (including a hand-rolled fake `httpx.AsyncClient` monkeypatched onto the real `httpx` module — the lazy `import httpx` inside the method still resolves to the patched module object) → FAIL (module didn't exist)
- [x] `ProviderResult`, `ModerationProvider` Protocol
- [x] `NullProvider`; `HeuristicProvider` (blocklist reuse + an exclamation-mark-spam ratio as the "pattern score" half of §12.4's "blocklist and pattern scores")
- [x] `OpenAIModerationProvider`, lazy `import httpx` mirroring `ResendProvider`
- [x] `build_provider()`
- [x] Verify: PASS (7 tests), ruff/mypy clean

---

### Task 8: `moderation/circuit_breaker.py` [independent]

**Satisfies:** §12.5 circuit breaker requirement.

**Files:** Create `backend/src/pickone/moderation/circuit_breaker.py`, `backend/tests/test_moderation_circuit_breaker.py`

- [x] Test: 7 cases written first → FAIL (module didn't exist)
- [x] `CircuitBreaker` (threshold, cooldown, injectable `Clock`), lazy-closes on `is_open()` once the cooldown has elapsed (no separate timer/scheduler needed). Module-level singleton via `get_circuit_breaker()`/`reset_circuit_breaker()`, mirroring `core/clock.py`
- [x] Verify: PASS (7 tests), ruff/mypy clean

---

### Task 9: `moderation/repository.py` + `moderation/service.py` [sequential]

**Satisfies:** §12.1 pipeline orchestration, §12.5 (moderation_results append-only, records policy_version/provider/model/latency_ms), acceptance criterion 3.

**Files:** Create `backend/src/pickone/moderation/repository.py`, `backend/src/pickone/moderation/service.py`, `backend/tests/test_moderation_service.py`

- [x] Test: 7 cases first (real DB via `db_session`, a minimal `Item` row constructed directly since `items/repository.py` doesn't exist yet — Task 2's ORM model is enough) → FAIL (module didn't exist)
- [x] `repository.py`: `create_moderation_result`
- [x] `service.py`: `moderate()` — circuit-breaker-open skips the call entirely (`provider_name="circuit_breaker"`, verified via a call-counting stub that asserts `calls == 0`); real timeout tested by monkeypatching `PICKONE_MODERATION_TIMEOUT_MS` down to 10ms against a provider that sleeps 1s, not just a generic-exception stand-in
- [x] Verify: PASS (7 tests), ruff/mypy clean. This closes out the moderation/ domain entirely — nothing left in it depends on items/.

---

### Task 10: `items/repository.py` [sequential]

**Satisfies:** Dedup lookup, slug-collision-safe insert, report bookkeeping, moderation queue queries.

**Files:** Create `backend/src/pickone/items/repository.py`, `backend/tests/test_items_repository.py`

- [x] Test: 11 cases first → FAIL (module didn't exist). Caught two test bugs along the way, not implementation bugs: (1) a shared `_insert` test helper reused the same `normalized_text` across calls, so the "distinct items" tests were colliding on the *dedupe* unique index rather than exercising slug collision; (2) `item_reports.reporter_user_id` has a real FK to `users.id`, so report tests needed actual `User` rows, not bare `new_uuid()` values
- [x] `insert_item_with_unique_slug` takes `item_id` (not `id`, to avoid shadowing the builtin), uses one `_build()` closure plus a single candidate list (`[base_slug, base_slug-2, ..., base_slug-99, base_slug-<hash>]`) tried in a loop under `session.begin_nested()` — no duplicated insert code between the numeric and hash-fallback paths
- [x] `set_item_status`, `create_report`/`count_distinct_reporters`, `list_moderation_queue`, `list_unresolved_reports_grouped` (returns `ReportGroup` dataclasses, grouped in Python from one joined query)
- [x] Verify: PASS (11 tests) — including a monkeypatched-`MAX_NUMERIC_SUFFIX_ATTEMPTS=2` test that forces the hash-suffix fallback path without actually creating 99 rows. Ruff/mypy clean.

---

### Task 11: `items/dependencies.py` + `items/schemas.py` [sequential]

**Satisfies:** Acceptance criterion 8 (exact 401/403 split and copy).

**Files:** Create `backend/src/pickone/items/dependencies.py`, `backend/src/pickone/items/schemas.py`, `backend/tests/test_items_dependencies.py`

- [x] Test: dependencies via a scratch FastAPI app (same pattern as `test_auth_dependencies.py`), schemas via direct construction, in two files → FAIL
- [x] `dependencies.py`: `item_author` combining `registered_user`'s guest check (with item-specific 401 copy) and `verified_user`'s check in one dependency
- [x] `schemas.py`: as planned. `CreateItemRequest.text`/`ReportRequest.reason` deliberately have only a generous DoS-safety `max_length` (1000/500) at the Pydantic layer — the real 2–64 business-rule length check stays entirely inside `items/validation.py` so the documented `invalid_text`/`too_long` reason codes are what actually fire, not a generic FastAPI validation error
- [x] Verify: PASS (3 + 6 tests). Needed `RegisterResult` doesn't expose the verify token directly (mirrors an existing M1 pattern) — read it from the outbox job payload via the same `_latest_email_token` helper `test_auth_verify.py` already uses. Ruff/mypy clean.

---

### Task 12: `items/service.py` [sequential]

**Satisfies:** The core creation transaction; acceptance criteria 1, 2, 3, 4, 7.

**Files:** Create `backend/src/pickone/items/service.py`, `backend/tests/test_items_create.py`

- [x] Test: 15 cases first → FAIL (module didn't exist)
- [x] `create_item()` returns the `Item` directly (no separate result wrapper — `item.status` already carries what the router needs, and adding a wrapper would just be a redundant field, so simplified from the plan's original `CreateItemResult`). Reserved-slug check is NOT duplicated here — `validation.validate_structure()` already covers it (Task 5), so by the time `create_item` reaches slug generation the text is already known-safe
- [x] **Found and fixed a real bug via mypy, not tests**: `insert_item_with_unique_slug` (Task 10) took a caller-supplied `item_id: str` parameter, but the only caller (`create_item`) passed `new_uuid()` — a `uuid.UUID`, not a `str` — and mypy correctly flagged the mismatch. The actual fix was to delete the parameter entirely: the function never needed a pre-generated id, since `Item`'s own `default=new_uuid` (already on the model since Task 2) handles it, exactly like every other model in the codebase. Simpler *and* type-correct, rather than papering over it with a type annotation change. Updated both call sites and Task 10's now-stale `item_id=new_uuid()` test arguments.
- [x] `report_item()`, `apply_moderation_decision()` as planned, using `items.errors.AlreadyReportedError` (added to Task 5's file, code=`already_reported`) rather than the generic `ConflictError`
- [x] Verify: PASS (12 items-service tests + 11 items-repository tests re-verified after the refactor = 23), full suite still green (218 tests), ruff/mypy clean

---

### Task 13: `test_items_concurrency.py` — the race test [sequential]

**Satisfies:** Acceptance criterion 7, explicitly named in the milestone's Tests section (`test_slug_collision_race`).

**Files:** Create `backend/tests/test_items_concurrency.py`

- [x] Test: 20 concurrent `create_item` calls (20 distinct fresh users, to keep per-user rate limits from interfering) against real separate connections via the `engine` fixture, not the savepoint-based `db_session` → **genuinely failed**, not a scaffolding gap: `RuntimeError: could not generate a unique slug`
- [x] **Found and fixed a real concurrency bug**, exactly what this test exists to catch: `insert_item_with_unique_slug`'s dedupe check (`get_item_by_normalized_text`) is a classic TOCTOU race — two concurrent transactions can both see "no existing row" under READ COMMITTED and both proceed to insert. The loser gets a real `IntegrityError`, but on `items_normalized_text_uq`, not `items_slug_uq` — and the old code caught *any* `IntegrityError` as "try the next slug suffix," so it burned through all 99 numeric candidates plus the hash fallback against a violation that retrying could never fix, and finally gave up with an opaque `RuntimeError` instead of the expected `409 already_exists`
- [x] Fix: added `NormalizedTextCollisionError` (a repository-internal signal, not an HTTP-facing error) and `_is_normalized_text_violation()`, which inspects the real constraint name. That took real digging — the constraint name isn't on `exc.orig` (SQLAlchemy's asyncpg DBAPI wrapper), it's one level deeper on `exc.orig.__cause__` (the actual `asyncpg.exceptions.UniqueViolationError`), confirmed empirically against a real Postgres connection rather than assumed. `items/service.py` catches this signal in one shared `_insert_or_raise_already_exists()` helper (used by both the blocklist-rejection and normal-insert call sites) and re-queries for the row that won the race, raising `AlreadyExistsError` with *its* slug — matching §4.5's "already here, here's the real one" contract exactly, including under a genuine race
- [x] Verify: PASS. Full items suite re-run after the fix (24 tests) plus the whole suite (243 tests) — all green, ruff/mypy clean.

---

### Task 14: `api/routers/items.py` [sequential]

**Satisfies:** §8.3, §8.5 (item + report routes), acceptance criteria 6, 8.

**Files:** Create `backend/src/pickone/api/routers/items.py`, Modify `backend/src/pickone/api/app.py`, `backend/tests/test_items_api.py`

- [x] Test: 13 cases first (full HTTP stack via `client`, CSRF headers included per the established `test_auth_api.py` pattern) → FAIL (404s, router didn't exist)
- [x] **Found and fixed a second real bug, this time via reasoning about the test *before* running it**, not from a failure: `item_author` (Task 11) depended on `required_actor`, which raises its own generic-copy `NotAuthenticatedError` for the "no session at all" case *before* `item_author`'s body ever runs — so a logged-out visitor with zero session would never see the item-specific "Make an account to add one." copy the milestone requires, only a guest *with* a session would. Fixed by depending on `current_actor` (`User | None`, never raises) instead, and handling `None`-or-guest as one case inside `item_author` itself. Added the missing "no session at all" case to Task 11's dependency tests (now 4 cases) to lock this in.
- [x] That fix exposed a second, separate finding that turned out to be *correct existing behavior, not a bug*: hitting `POST /api/items`/`.../report` with literally no session cookie returns `403 csrf_failed` from `CSRFMiddleware`, not `401` — confirmed by grepping `test_csrf.py`, where this is already established, tested M1 behavior (CSRF default-deny runs before any route dependency for a non-allowlisted unsafe method). `item_author`'s "no session" branch is still correct and exercised — it's just genuinely reachable only for a *guest* (who has a session and clears CSRF) or from a bare dependency-only scratch app without the middleware, not from a literally-sessionless request against the real app. Added a real, CSRF-respecting guest test using `create_guest()` + `derive_csrf_token()` to prove the actual reachable path end-to-end, and retitled/corrected the two sessionless tests to assert the real `403 csrf_failed`.
- [x] `POST /api/items`, `GET /api/items/{slug}` (reduced schema: `rank`/`ranked` present as `null`/`false`, `rivals` absent entirely), `POST /api/items/{slug}/report`; registered in `api/app.py`
- [x] Verify: PASS (13 items-api + 4 items-dependencies re-verified), full suite green (256 tests), ruff/mypy clean

---

### Task 15: `api/routers/admin.py` — JSON admin API [sequential]

**Satisfies:** §8.5 JSON contract, §12.6 auditability (append-only decisions).

**Files:** Create `backend/src/pickone/api/routers/admin.py`, Modify `backend/src/pickone/api/app.py`, `backend/tests/test_admin_api.py`

- [x] Test: 6 cases first → FAIL (404s, router didn't exist)
- [x] Small precursor addition to Task 9's `moderation/repository.py`: `get_latest_result_for_item()`, needed so the queue can show scores. Writing its own test first surfaced that `create_moderation_result` relied on Postgres's `server_default=func.now()` for `created_at` — which freezes to the *transaction's* start time, so two inserts in the same transaction get an *identical* timestamp and `ORDER BY created_at DESC LIMIT 1` can't reliably tell them apart. This is exactly the M1 "clock gotcha" already documented in CLAUDE.md, just newly triggered here — fixed by setting `created_at=get_clock().now()` explicitly, matching every other timestamped insert in the codebase.
- [x] **Found and fixed a real multi-actor test-isolation bug** while writing the queue/decision/reports tests: switching between three logged-in users (creator → admin → reporter) via repeated `_verified_member()` calls overwrites the shared `client`'s session cookie each time, so acting as an *earlier* user later sends a stale CSRF token paired with the *current* (different) session — a guaranteed `403 csrf_failed`, not a real assertion failure, so it would have silently made every multi-actor test worthless rather than failing loudly in an obvious way. Fixed by having `_verified_member()` return the raw session token alongside the CSRF token, and an explicit `_switch_to(client, raw_token)` helper before each actor-specific call.
- [x] **Found and fixed a second, more structural bug** from the same work: the circuit breaker is a process-global singleton, and I'd been adding an autouse "reset before each test" fixture *per test file* (Tasks 9/12/13). That only resets going into files that declare it — a test in one file that opens the breaker and never closes it can leak into a *different* file's tests that never touch the breaker at all, and pytest's default alphabetical collection order means `test_admin_api.py` (which forces REVIEW by opening the breaker) runs before `test_items_api.py` (which asserts a plain `APPROVED` outcome) — a real risk of one file's state silently breaking another's assertions. Moved the fixture to a single autouse fixture in `conftest.py` (reset before *and* after every test, matching the reference `_reset_app_engine_cache` fixture's shape) and deleted the now-redundant per-file copies in Tasks 9/12/13's test files.
- [x] `GET /api/admin/moderation/queue`, `GET /api/admin/reports`, `POST /api/admin/items/{id}/decision`; registered in `api/app.py`
- [x] Verify: PASS (6 admin-api + re-verified 20 tests across the three files touched by the breaker-fixture move), full suite green (265 tests), ruff/mypy clean

---

### Task 16: `app/admin/*` — Next.js admin pages [sequential]

**Satisfies:** §12.6 (the actual "smallest thing that works" UI), `noindex,nofollow`.

**Files:** Modify `frontend/lib/api.ts` (add `is_admin` to `UserOut`, admin types), Modify `backend/src/pickone/auth/schemas.py` (`UserOut.is_admin`), Create `frontend/app/admin/layout.tsx`, `frontend/app/admin/moderation/page.tsx`, `frontend/app/admin/reports/page.tsx`, Modify `frontend/components/Nav.tsx` (admin link, `is_admin`-gated), `backend/tests/test_auth_api.py`

- [x] Test: `test_me_exposes_is_admin` written first → FAIL (`KeyError: 'is_admin'`)
- [x] Added `is_admin: bool` to `UserOut`/`UserOut.from_user`
- [x] `frontend/lib/api.ts`: `UserOut.is_admin` plus the queue/reports/decision response types
- [x] `frontend/app/admin/layout.tsx`, `app/admin/moderation/page.tsx`, `app/admin/reports/page.tsx` — client components against the JSON API from Task 15
- [x] `Nav.tsx`: "Admin" link inside the existing dropdown, gated on `user.is_admin`
- [x] Verify: PASS (`test_auth_api.py` 7/7, full backend suite 266), `tsc`/`eslint`/`next build` all clean
- [x] **Did not defer the manual check to Task 21** — did it now, live, against the real `docker compose` stack, since a bug at this layer would otherwise sit undiscovered through several more tasks. Registered a real user via the actual `/register` UI, promoted to admin via direct SQL (matching the spec's "no self-service" rule), and drove both admin pages for real: created an item via the live API, forced it into `REVIEW` via SQL (the real `/add` page doesn't exist until Task 20, so this is the equivalent of a provider genuinely flagging it), approved it through the **Approve** button, confirmed the DB reflects `APPROVED`/`published_at` set, reported a different item and confirmed it appeared correctly grouped on the reports page.
- [x] **Found and fixed a real bug this way, not from an automated test**: both admin pages only treated a `404` `ApiError` as "not admin, show blocked state" — but `admin_user`'s dependency chain raises `401 account_required` first for a *logged-out* visitor (`required_actor` fires before `admin_user`'s own 404-for-non-admin check ever runs), a case no automated test in this plan happened to cover for the *frontend* pages specifically. A logged-out visitor hitting either admin page got neither the item list nor the blocked state — it hung on "Loading." forever, since the `catch` block's `if (status === 404)` check silently swallowed the 401 and never called `setNotFound`. Fixed by treating 401 the same as 404 in both pages' error handling, re-verified live in the same browser session.
- [x] Cleaned up all test data created against the dev database afterward.

---

### Task 17: Creation rate limits — boundary tests [sequential]

**Satisfies:** §12.7, explicitly named in the milestone's Tests section.

**Files:** Create `backend/tests/test_items_ratelimits.py`

- [x] Hourly/new-account/established-daily boundaries were already exercised in Task 12; this task's job was specifically the per-IP dimension (untested until now) and the `retry_after`/headers assertion the milestone's Tests section calls out explicitly (Task 12 only checked that `RateLimitedError` was raised, not its payload)
- [x] Per-IP daily limit boundary + isolation-across-IPs, both via monkeypatched low limits (matching Task 12's pattern) rather than actually creating 50+ rows
- [x] Verify: PASS (3 tests) — passed on the first run, since this only added *coverage*, not new implementation (the per-IP enforcement itself was already correct from Task 12)

---

### Task 18: import-linter contract for `items/`/`moderation/`/`admin/` [independent]

**Satisfies:** Milestone brief's "must not create backwards dependencies" requirement.

**Files:** Modify `backend/pyproject.toml`

- [x] Baseline confirmed green (3 contracts kept) before adding the new one
- [x] Added contract: `moderation/` never imports `items/`
- [x] Verify: 4 contracts kept, 0 broken; `test_boundaries.py` and the full suite (269 tests) still green

---

### Task 19: `/me` — real `items_remaining_today` [sequential]

**Satisfies:** Locked-in decision from the pre-plan discussion — closes the M1 placeholder gap that M2 itself causes.

**Files:** Modify `backend/src/pickone/api/routers/auth.py`, `backend/tests/test_auth_api.py`

- [x] Test: `test_me_items_remaining_today_reflects_real_usage` written first → FAIL (hardcoded to the full limit, didn't decrease after creating an item)
- [x] Extracted `effective_daily_item_limit()` and `daily_rate_limit_key()` from `items/service.create_item` into standalone functions so `me_route` reuses the *exact* same key and new-account-cap logic rather than recomputing it — a duplication `create_item` and `me_route` would otherwise both own. `me_route` now does `ratelimit.peek()` against that key and returns `max(effective_limit - count, 0)`. This introduces `pickone.auth`'s router importing from `pickone.items` — checked against the import-linter contracts first: nothing forbids it, and it matches the existing pattern of routers freely crossing domain boundaries (e.g. `api/routers/admin.py` already imports both `items` and `moderation`).
- [x] Verify: PASS (full auth suite 8/8, items suite re-verified 16 tests), import-linter still 4/4 kept, full suite green (270 tests), ruff/mypy clean

---

### Task 20: Frontend `/add` page [sequential]

**Satisfies:** §4.5 exactly, acceptance criterion 6.

**Files:** Modify `frontend/app/add/page.tsx`, `frontend/lib/api.ts` (add `ItemOut`/`CreateItemResponse` types + helper), `frontend/tests` (if a frontend test runner exists — otherwise this is verified live per Task 22)

- [x] No unit test runner in this repo — but rather than deferring all verification to Task 21, drove the real page live now: split into a thin server `app/add/page.tsx` (owns the `noindex,nofollow` metadata, which a "use client" file can't export) and a new `components/AddForm.tsx` client component holding the actual form logic
- [x] Guest/logged-out redirect, the 2–64/counter-at-48/tooltip form, and all five response cases (201/202/409/422 rejected/422 invalid_text) implemented per §4.5's exact copy
- [x] On `201`: shows "Added." for 800ms then redirects to `/play?seed={item_id}`
- [x] Purged the old JSDoc comment block from the M0 placeholder
- [x] Verify: `tsc`/`eslint`/`next build` all clean, **then drove the real page live** against the real `docker compose` stack rather than waiting for Task 21 — registered+verified a fresh user through the actual UI, and exercised all five outcomes for real: a clean approval (confirmed the "Added." → 800ms → `/play?seed=<real-item-id>` redirect via `window.location.href`), a duplicate (confirmed "Already here." with a working `See it` link to `/item/{slug}`), and a blocklisted submission ("We can't add that one."). Cleaned up all test data afterward.
- [x] **Process note, not a product bug**: one click missed the submit button because a screenshot's reported pixel coordinates and the page's actual CSS pixel coordinates weren't at the same scale — clicking by element `ref` (from `read_page`) instead of raw screenshot coordinates resolved it immediately. Worth remembering for any future live-browser pass in this project: prefer `ref`-based clicks over coordinate guesses from a screenshot.

---

### Task 21: Full gate + live verification [sequential]

**Satisfies:** Milestone definition of done.

- [x] `uv run pytest` → 270 tests, all green
- [x] `make lint` → green (ruff check, ruff format --check, mypy 107 files, import-linter 4/4 kept, eslint, tsc) — one stale `# type: ignore[arg-type]` in `test_items_schemas.py` had gone unused after an earlier refactor and `warn_unused_ignores` caught it; removed
- [x] `npm run build` → succeeds, both admin routes present in the route table
- [x] Live verification: rather than one big pass deferred to the end, this was done incrementally as each task landed (Task 16 for admin, Task 20 for `/add`) so a bug at either layer wouldn't sit undiscovered through several more tasks — see those tasks' notes for the two real bugs found and fixed that way. This final pass covers what those didn't:
  - `curl` against the live API directly (not through the frontend): `GET /api/items/{unknown-slug}` → `404 not_found`; `POST /api/items` with no session/cookie at all → `403 csrf_failed` (the already-established CSRF-first architecture, not a new check, but worth confirming against the real running stack rather than only the test suite)
  - Revised the original plan wording here: it called for confirming a guest's `401 account_required` "directly via curl", but Task 14's own investigation already established that's not achievable by curl alone — a guest actor needs a real session, and no HTTP-reachable endpoint creates one until M4's `GET /api/battles/current` ships. That case is covered instead by `test_guest_with_a_real_session_gets_401_account_required` (Task 14, using `create_guest()` + `derive_csrf_token()` against the full CSRF-respecting stack) and was not re-litigated here.
  - Cleaned up all live-verification test data from the dev database throughout

## Corrections

<!-- Append-only log of mid-flight course corrections -->
