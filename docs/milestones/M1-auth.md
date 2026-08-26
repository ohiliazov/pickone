# M1 — Authentication & accounts

**Size:** M · **Depends on:** M0 · **Parallel with:** M3
**Spec reference:** [§4.1](../SPEC.md#41-registration-and-guest-conversion), [§8.2](../SPEC.md#82-authentication), [§13.1](../SPEC.md#131-authentication), [§13.3](../SPEC.md#133-csrf), [§13.4](../SPEC.md#134-rate-limits)

## Goal

Actors. A visitor gets a guest identity the moment they need one; a guest becomes a member without losing a thing; a member can verify, log in, log out, reset their password and delete themselves completely. Sessions are server-side, revocable and CSRF-protected. Every auth endpoint is rate limited and does not leak whether an account exists.

## Scope

- `auth/` module: actor creation (guest **and** registered), Argon2id hashing with rehash-on-login, session issue/validate/revoke, email tokens.
- **Guest actors** ([§4.0](../SPEC.md#40-the-first-pick--no-account-required)): `create_guest()` returns an ordinary `users` row with `is_guest = true` and issues a session exactly as login does. It is called from exactly one place — M4's battle read — and is exposed here as a service function, not an endpoint.
- **Guest conversion** ([§4.1](../SPEC.md#41-registration-and-guest-conversion)): registering while holding a guest session is an **`UPDATE` on that row** — same `user_id`, same battles, same sessions. Never a copy-and-merge. Registering with an already-taken email while holding a guest session returns `409`; **do not auto-merge two identities.**
- Session middleware and a **four-tier** dependency ladder, so later milestones just declare what they need:
  `current_actor` (guest or member, creates nothing) · `required_actor` · `registered_user` (401 for guests, with `account_required`) · `verified_user` · `admin_user`.
- **Account deletion** ([§13.7](../SPEC.md#137-account-deletion-and-the-audit-trail)): the exact transaction in the spec — expire any pending battle, revoke sessions, delete tokens, NULL out `items.created_by_user_id` / `item_reports.reporter_user_id` / `analytics_events.user_id`, then **`DELETE FROM users`**. `battles.user_id` becomes `NULL` via `ON DELETE SET NULL`. Registered users only; a guest cannot delete (there is nothing to delete, and the janitor handles it).
- **The guest janitor** (worker job): delete guests with zero completed battles and `last_seen_at` older than `GUEST_EMPTY_TTL_DAYS = 7`; delete guests older than `GUEST_MAX_AGE_DAYS = 180` regardless, leaving their battles with a `NULL` actor. Never touches a registered user.
- CSRF middleware: **default-deny** on all unsafe methods with an explicit allowlist, per [§13.3](../SPEC.md#133-csrf). Origin/Referer check.
- Rate-limit middleware backed by the `rate_limits` table, with a decorator taking a named limit from the config register.
- `EmailProvider` protocol + `ResendProvider` + `ConsoleProvider` (local) + `OutboxProvider` (writes to `outbox_jobs`; the worker sends). Two templates: verify, reset.
- Worker job: outbox runner (`FOR UPDATE SKIP LOCKED`, exponential backoff, max attempts, dead-letter via `last_error`).
- Rate limits including **guest creation: 300/hour/IP** ([§13.4](../SPEC.md#134-rate-limits)).

**Note:** the unverified-play grace window from the earlier draft is **gone**. Guests play without limit, so gating *members* on verification would make registering strictly worse than not registering. Verification gates item creation only.

## Database changes

`users`, `sessions`, `email_tokens`, `rate_limits`, `outbox_jobs` exactly as specified in [§7.2](../SPEC.md#72-core-tables)/[§7.3](../SPEC.md#73-supporting-tables), including `users_credentials_ck`, `last_seen_at`, and `users_guest_reap_idx`.

## API changes

All of [§8.2](../SPEC.md#82-authentication): `register` (with `converted_from_guest` and `picks_kept` in the 201 body), `login`, `logout`, `verify`, `verify/resend`, `password-reset/request`, `password-reset/confirm`, `GET /api/me` (returns `is_guest`). Plus `POST /api/me/delete`.

## Frontend changes

`/register`, `/login`, `/forgot`, `/reset`, `/verify` — plain, minimal, in the product lexicon ([§5.6](../SPEC.md#56-copy-and-terminology)). All `noindex,nofollow`. A CSRF-token-aware fetch wrapper, and an auth context that the nav uses to show `Log in` vs the avatar menu (with the "Slower pace" toggle from [§5.7](../SPEC.md#57-accessibility-wcag-22-aa--a-launch-requirement-not-a-follow-up)).

## Tests

- Argon2 params produce a 150–300ms hash on CI hardware (asserted as a range, skipped if the runner is atypical); rehash-on-param-change works.
- Registration: happy path, duplicate email → `409`, weak password → `422`, rate limit → `429`.
- Login: happy path; unknown email and wrong password return **byte-identical** responses and take comparable time; account lockout backoff; new session id issued (fixation).
- Verification: happy path, expired token → `410`, reused token → `400`, resend rate limit.
- Reset: request always `202` for known and unknown emails; confirm revokes **all** sessions; token single-use.
- Session: revoked session rejected on the next request; sliding expiry extends; absolute cap terminates.
- CSRF: unsafe request without the header → `403`; with a mismatched token → `403`; with a foreign `Origin` → `403`; a `GET` needs none. **A test asserts that a newly added unsafe route is denied by default** (add a fixture route and assert `403`).
- Rate limits: each configured limit enforced, `Retry-After` present, counters isolated per key.
- Outbox: a job is written, the worker sends it once, a failure retries with backoff, `max_attempts` dead-letters.
- Enumeration: no endpoint's status code, body or timing distinguishes a known from an unknown email.
- **Guest conversion:** a guest with 10 battles registers → same `user_id`, `is_guest` false, email set, all 10 battles still attached, `picks_kept == 10`.
- Registering with a taken email while holding a guest session → `409`, and **the guest row is untouched** (no partial write, no merge).
- Logging out a member and calling a guest-creating path issues a **new** guest; a member's session is never downgraded.
- **Deletion** ([§13.7](../SPEC.md#137-account-deletion-and-the-audit-trail)): after deleting an actor with battles — zero `users` rows, zero sessions, zero tokens, `items.created_by_user_id` NULL, `item_reports.reporter_user_id` NULL (**and the item's report count unchanged, so it does not un-hide**), and every `battles` row still present with `user_id IS NULL`.
- Deleting an actor holding a `PENDING` battle leaves the partial unique index usable by a new actor.
- **Janitor:** reaps only guests with zero completed battles past the TTL; never a registered user; never a guest with battles inside `GUEST_MAX_AGE_DAYS`.
- Guest creation is rate limited per IP.

## Acceptance criteria

1. Full guest → play → register → verify → login → logout → reset → login → delete cycle passes end to end against real Postgres, with the guest's history intact after conversion.
2. No auth response distinguishes existing from non-existing accounts.
3. An unsafe endpoint added without an explicit allowlist entry is rejected by CSRF middleware — proven by a test.
4. `sessions.token_hash` and `email_tokens.token_hash` never store a plaintext token (asserted by inspecting the row after issue).
5. Password reset invalidates every existing session for that user.
6. `users_credentials_ck` rejects a non-guest row with a null email, at the database level, and permits a guest row with both null.
7. Rate limits on all seven auth endpoints plus guest creation, values from the register.
8. Deleting an account destroys every trace of the person and **changes no rating, no counter and no `rating_events` row** — asserted by a byte-comparison before and after.

## Non-goals

OAuth/social login, 2FA, magic links, user profiles as pages, avatars, usernames, admin UI, email change flow, account recovery beyond password reset, `is_admin` self-service. **Merging two identities** (guest + existing account) — that is a real product feature with real edge cases and it is not this milestone's, or this MVP's. **Any unverified-play gate on registered users.**
