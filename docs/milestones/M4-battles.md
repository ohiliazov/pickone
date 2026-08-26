# M4 — Comparisons, matchmaking & battle lifecycle

**Size:** L — **the hard one** · **Depends on:** M2, M3
**Spec reference:** [§6](../SPEC.md#6-domain-model), [§8.4](../SPEC.md#84-the-battle-loop), [§9](../SPEC.md#9-battle-state-machine) in full, [§11](../SPEC.md#11-matchmaking), [§16.3](../SPEC.md#163-concurrency-tests--the-ones-that-matter-most)

## Goal

The core of the product: **every actor always has exactly one standing pair waiting for them**, it expires in under a minute, and resolving it is atomic and exactly-once — correct under concurrent tabs, double clicks, retries, multiple workers, and visitors who have no account at all.

**Over-invest here.** Every bug in this milestone is silent, permanent and corrupts data that cannot be reconstructed. Later polish repairs none of it.

## Scope

- `comparisons/`: canonicalisation (`item_a_id < item_b_id`), get-or-create via `ON CONFLICT … DO UPDATE … RETURNING`, comparison slug generation from the two item slugs in database-canonical order.
- `matchmaking/`: the `PairSelector` protocol defined in M3, implemented against SQL. The three strategies with configurable weights, the eligibility filters, the down-weighting of the requester's own items, the relaxation ladder, and the `?seed=` handling. **No import of `rating/`.**
- `battles/state.py`: the state machine as explicit, testable transitions. Illegal transitions raise, they do not silently no-op.
- `battles/service.py`: the two transactions, implemented exactly as in [§9.3](../SPEC.md#93-the-standing-pair-invariant) and [§9.4](../SPEC.md#94-battle-completion--the-atomic-transaction) — advisory lock, unique-violation-as-success on read-repair; `FOR UPDATE` with **ascending id ordering**, validation order, pure rating call, five writes, `rowcount` assertion on completion.
- **Guest actors** ([§4.0](../SPEC.md#40-the-first-pick--no-account-required)): `GET /api/battles/current` with no session calls M1's `create_guest()`, issues the cookie, and proceeds identically. **This is the only place in the codebase that creates a guest.** Everything downstream is keyed on `user_id` and must contain no `is_guest` branch.
- The chosen `RatingSystem` from M3, wired in behind its protocol. `battles/` calls `apply()` and writes `Rating(value, deviation)` for both items plus the `terms` payload — it never contains a formula.
- Skip: the same shape minus the rating work, plus skip counters.
- Lazy expiry on every read and mutation; the sweeper job in the worker (`SWEEPER_INTERVAL_SECONDS`).
- `next`-battle creation in a **separate transaction** after the pick commits; failure omits `next` and never rolls back the pick.
- Idempotent replay: a duplicate pick with the same `winner_id` returns the stored result with `200`.
- Deleted actors: `battles.user_id` is nullable, so every query in this module must tolerate `NULL` and the reconciliation job must not read it as corruption ([§13.7](../SPEC.md#137-account-deletion-and-the-audit-trail)).
- Metrics from [§17.5](../SPEC.md#175-observability): `battle_deadlocks_total`, `battle_transaction_retries_total`, `rating_clamp_total`, `matchmaking_*`, `pending_battles_gauge`.
- Nightly reconciliation job ([§17.5](../SPEC.md#175-observability)) — report, never repair.

## Database changes

`comparisons` (with `comparisons_canonical_ck`, `comparisons_pair_uq`, `comparisons_slug_uq`, the three secondary indexes), `battles` (nullable `user_id` with `ON DELETE SET NULL`, `battles_winner_ck`, `battles_expiry_ck`, **`one_pending_battle_per_user` including `AND user_id IS NOT NULL`**, the RD snapshot columns, `rating_system_version`, and the four secondary indexes), `rating_events` (with RD columns, the `terms` JSONB, and `rating_events_battle_item_uq`). Grant the application role no `UPDATE`/`DELETE` on `rating_events`.

## API changes

`GET /api/battles/current` (+ `?seed=`), `POST /api/battles/{id}/pick`, `POST /api/battles/{id}/skip` — every response and every error code from [§8.4](../SPEC.md#84-the-battle-loop).

## Frontend changes

Minimal and deliberately ugly: an unstyled `/play` that fetches a battle, renders two `<button>`s and a Skip, posts the result, and renders `next`. **This exists to prove the API, not to be the game.** M5 replaces it entirely. Do not spend time here.

## Tests

This milestone's test suite is its main deliverable. All against real Postgres, no mocks.

**Every concurrency test in [§16.3](../SPEC.md#163-concurrency-tests--the-ones-that-matter-most)**, verbatim — `test_concurrent_battle_creation`, `test_double_click_pick`, `test_conflicting_picks`, `test_pick_and_skip_race`, `test_deadlock_free_opposite_pairs`, `test_expiry_race`, `test_sweeper_vs_pick`, `test_comparison_get_or_create_race`, `test_counter_consistency`.

State machine:
- Every legal transition applies; every illegal one raises and changes nothing.
- No transition out of any terminal state exists — a parameterised test over all three terminal states × all three actions.

Expiry (using the injectable clock — **no `sleep` in any test**):
- A pick at `expires_at - 1ms` succeeds; at `expires_at + 1ms` returns `410` with both ratings byte-identical.
- An expired pending battle is transitioned lazily on the next read even with the sweeper stopped.
- The sweeper transitions abandoned battles and is idempotent.

Ownership and validation:
- User B picking user A's battle → `404`.
- `winner_id` not in the comparison → `422`, nothing written.
- Malformed/absent `winner_id` → `422`.

Idempotency:
- Same `winner_id` twice → two identical `200`s, one rating application, exactly two `rating_events` rows.
- Different `winner_id` second → `409`, ratings unchanged from the first application.

Matchmaking:
- Strategy weights are honoured within tolerance over 10,000 draws.
- **`RANDOM_WEIGHT ≥ 0.25`** asserted against the config — the fun is a tested requirement. [§11.1](../SPEC.md#111-strategy-mix)
- Every eligibility filter excludes what it should; the relaxation ladder fires in order; exhaustion returns `503`.
- Only `APPROVED` items are ever selected (property test over a mixed pool).
- `?seed=` uses the item once, validates it, and rejects a seed that is unapproved or nonexistent.
- Never returns the same item twice in one pair.

**The `[P4]` guard:** `test_current_battle_exposes_no_ratings` — assert the serialised response schema contains no key matching `rating|deviation|rank|win|loss|battle_count|score`, by key inspection, not by reading the model. This test must fail if anyone adds such a field.

**Guest actors:**
- `test_concurrent_guest_creation` — 20 parallel cookie-less reads → 20 distinct guests, each with exactly one pending battle, **none with two**.
- A cookie-less read returns a battle *and* a `Set-Cookie`; a second read with that cookie returns the **same** `battle_id`.
- A guest's pick moves ratings exactly as a member's does — same code path, asserted by comparing `rating_events` rows.
- `test_conversion_race` — registration and a pick submitted simultaneously on one guest session: both succeed, one rating application, `is_guest` ends `false`.
- A grep-level test asserting `battles/` contains no reference to `is_guest`.

Boundary: an automated check that `matchmaking/` does not import `rating/`.

## Acceptance criteria

1. 20 concurrent `GET /battles/current` for one user → exactly one `PENDING` row and 20 identical `battle_id`s.
2. Double-submitted picks move each item's rating **exactly once**, proven by recounting `rating_events`.
3. 50 concurrent battles over overlapping pairs produce **zero** deadlocks.
4. An expired battle changes no rating, ever, under any race.
5. `one_pending_battle_per_user` is proven to be the enforcing mechanism: with the application-level check deliberately removed in a test build, concurrent creation still yields one battle.
6. `GET /api/battles/current` exposes no rating-like field, deviation included.
6a. A visitor with no cookie can complete a battle end to end, and it counts.
7. After 1,000 random concurrent operations, all denormalised counters on `items` and `comparisons` match a recount from `battles` exactly.
8. `pick` p95 latency < 200ms with 100 concurrent users on the load-test rig.
9. `battles/` has 100% line and branch coverage.

## Non-goals

Any UI polish, animation, keyboard or gesture handling (M5). Public pages (M6). Battle history for users. Undo. Rematch. Category-aware or personalised matchmaking. Bandit/information-gain selection. Retroactive rating recomputation. Auto-repair in the reconciliation job.
