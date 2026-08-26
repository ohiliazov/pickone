# M2 — Items & moderation

**Size:** M · **Depends on:** M1 · **Parallel with:** M3
**Spec reference:** [§4.5](../SPEC.md#45-add-one), [§8.3](../SPEC.md#83-items), [§12](../SPEC.md#12-moderation), [§14.3](../SPEC.md#143-url-and-slug-strategy)

## Goal

A verified user can add a plain-text item. It is normalised, deduplicated, slugged, moderated by a pretrained model, and either published at rating 100 or held for review — and the whole thing feels like typing a phrase and reading the word "Added."

## Scope

- `items/`: normalisation (`display_text`, `normalized_text` — both pure, both heavily tested), structural validation, slug generation with collision handling and the `-vs-` → `-versus-` substitution, repository, creation service.
- `moderation/`: the `ModerationProvider` protocol; `OpenAIModerationProvider`, `HeuristicProvider`, `NullProvider`; the versioned policy mapping; the circuit breaker; the service that orchestrates provider → policy → decision and writes `moderation_results`.
- Item creation transaction: validate → normalise → dedupe → blocklist pre-filter → provider call (`MODERATION_TIMEOUT_MS`) → policy → insert item + moderation result → set `status` and `published_at`. All in one transaction; a provider timeout yields `REVIEW`, never a failed request.
- **The one hard gate in the product:** `POST /api/items` requires `verified_user`. A guest gets `401 account_required` with the copy *"Make an account to add one."* — not `403`, because the gate is authentication and the message should name it.
- Admin surface ([§12.6](../SPEC.md#126-admin-review)): queue, decision, reports. Server-rendered, `is_admin`-gated, `noindex,nofollow`. Three screens, nothing more.
- `POST /api/items/{slug}/report` (registered only) and the auto-hide-at-N-reports rule. **Reporting is reachable only from an item page — never from `/play`.** A report control beside the cards is a second primary verb and a way to avoid deciding. `[P1]` `[P2]`
- Creation rate limits ([§12.7](../SPEC.md#127-rate-limits-on-creation)).

## Database changes

`items` (with `items_text_len_ck` at **64**, `items_counts_ck`, `items_rating_ck`, `items_rd_ck`, the unique indexes on `normalized_text` and `slug`, and all four secondary indexes), `moderation_results`, `item_reports` (with `reporter_user_id` **`ON DELETE SET NULL`** and the partial unique index) — per [§7.2](../SPEC.md#72-core-tables)/[§7.3](../SPEC.md#73-supporting-tables).

`items.rating` defaults to **`0.0000`** ([§10.4](../SPEC.md#104-zero-is-the-origin-and-the-sign-is-the-product) — zero is the origin, not "unrated") and **`items.rating_deviation` to `350.0000`**; both come from the config register and the defaults are asserted to match. The deviation column ships now, before any rating code exists, because adding it later means a migration on the largest table in the database ([§10.2](../SPEC.md#102-the-three-candidate-systems)).

## API changes

`POST /api/items`, `GET /api/items/{slug}` (JSON only in this milestone — the page is M6), `POST /api/items/{slug}/report`, `GET /api/admin/moderation/queue`, `POST /api/admin/items/{id}/decision`.

## Frontend changes

`/add`: the exact copy from [§4.5](../SPEC.md#45-add-one) — *"What should we add?"*, one input, `[ Add one ]`, character counter appearing at **48** against a **64** limit. A guest or logged-out visitor hitting `/add` is sent to `/register` first — the only redirect-to-auth in the product. The counter's tooltip answers *"Why 64 characters?"* with **"That's why."** ([§12.3](../SPEC.md#123-structural-validation)). All five response cases handled with their specified copy. On `201`, show "Added." for 800ms then redirect to `/play?seed={item_id}` (the parameter is honoured in M4; M2 just sets it). `+ Add one` wired into the nav.

## Tests

- Normalisation: a table-driven suite covering whitespace runs, leading/trailing space, zero-width and bidi characters, combining marks (`café` → `cafe`), casefolding of non-ASCII, emoji, mixed scripts, and C0/C1 controls. `normalized_text` is idempotent and stable.
- Validation: every rule in [§12.3](../SPEC.md#123-structural-validation) has a passing and a failing case. Reserved slugs rejected.
- Slugs: collision → `-2`, `-3`; 99 collisions → hash suffix; a 64-char truncation lands on a word boundary; text containing `-vs-` produces a slug containing `-versus-`; **a slug can never be parsed as a comparison slug** (property test).
- Dedupe: two items differing only in case/punctuation/accents → the second gets `409` with the existing slug.
- Policy: a table mapping synthetic score vectors to `APPROVED`/`REVIEW`/`REJECTED` at every threshold boundary, both sides.
- Provider: timeout → `REVIEW` + `202`; exception → `REVIEW`; the circuit breaker opens after N failures, holds for 60s, and closes.
- `NullProvider` cannot be selected when `ENV=production` — asserted at config validation.
- Moderation results are append-only and record `policy_version`, `provider`, `model`, `latency_ms`.
- Admin: non-admin gets `404` on every admin route; a decision writes a new `moderation_results` row with `reviewed_by_user_id` and never mutates the previous one; approval sets `published_at`.
- Reports: duplicate report by the same user → `409`; the Nth distinct report sets `HIDDEN` and enqueues review.
- Rate limits: hourly, daily, per-IP, and the tighter new-account cap.
- Concurrency: 20 parallel creations of the same text → exactly 1 item, 19 × `409` (`test_slug_collision_race`).
- Escaping: an item containing `<script>alert(1)</script>`, `"`, `'` and RTL overrides round-trips safely through the JSON API and the admin HTML.

## Acceptance criteria

1. An approved item exists with `status='APPROVED'`, `rating=0`, `rating_deviation=350`, `published_at` set, and a unique slug. **No code path treats `rating == 0` as "missing"** — a lint rule bans truthiness tests on ratings.
2. A near-duplicate is refused with a link to the original.
3. With the moderation provider unavailable, creation still returns `202` and the item is **not** public.
4. An item rejected by the provider is never visible anywhere and its response body contains no category or score.
5. `ENV=production` + `NullProvider` fails at boot.
6. The `/add` flow uses only the copy in [§5.6](../SPEC.md#56-copy-and-terminology) — verified by a test asserting the rendered strings.
7. Slug generation is race-safe under 20 concurrent identical submissions.
8. A guest attempting to add an item gets `401 account_required`; an unverified member gets `403`; both messages are in the product lexicon.
9. `items_text_len_ck` rejects 65 characters and accepts 64, at the database level.

## Non-goals

Item editing or renaming, deletion by users, images, categories, tags, emoji-only items, non-Latin scripts, fuzzy or semantic dedupe (Phase 3), bulk import, a public item page (M6), any rating change (M4), search or autocomplete, ML moderation training, moderator roles beyond `is_admin`.
