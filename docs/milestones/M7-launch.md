# M7 — Analytics, hardening, seed data & launch

**Size:** M · **Depends on:** M5, M6
**Spec reference:** [§11.4](../SPEC.md#114-cold-start-and-the-catalogue-floor), [§13](../SPEC.md#13-security-and-anti-abuse), [§15](../SPEC.md#15-analytics), [§16.6](../SPEC.md#166-load-testing), [§17.4–17.5](../SPEC.md#174-deployment)

## Goal

Turn a correct system into a launched product: measured, observable, load-tested, secured, seeded with enough items to be fun on day one, and operable by a human at 3am.

## Scope

**Analytics ([§15](../SPEC.md#15-analytics))** — **every core metric segmented by `is_guest`**, including guest→registered conversion and the guest-vs-registered agreement metric whose 5pp threshold triggers [§13.6](../SPEC.md#136-guest-play-and-anti-abuse)'s escape hatch.
- The `play session` SQL view (30-minute gap rule) — defined **once**, so no two numbers ever disagree.
- Versioned SQL views for every metric in [§15.3](../SPEC.md#153-the-metrics-that-matter), all derived from `battles`, not from client events.
- `POST /api/events` ingest for the client-only events listed in [§15.1](../SPEC.md#151-source-of-truth), batched with `sendBeacon`, rate limited, no PII.
- The daily rollup job writing `daily_metrics`, and the 180-day pruning job for `analytics_events`.
- `docs/analytics.md`: every event, every property, every metric definition.
- A dashboard (PostHog or a handful of SQL views behind the admin surface) showing the north-star metrics.

**Hardening ([§13](../SPEC.md#13-security-and-anti-abuse))**
- Full security header set, CSP with a nonce and no `unsafe-inline` for scripts, HSTS with preload.
- A security review pass against [§13](../SPEC.md#13-security-and-anti-abuse) with each control checked off and evidenced.
- Abuse monitors: battles per actor per hour, share of a comparison's battles from one actor or /24, item-creation spikes, guest-creation rate per IP. **Alert only — no auto-blocking in MVP.**
- The **guest janitor** and the **rating-recompute-excluding-guests** capability from [§13.6](../SPEC.md#136-guest-play-and-anti-abuse), the latter as a tested offline script — the escape hatch must be proven to work *before* it is needed, not improvised during an incident.
- The nightly reconciliation job wired to alerting ([§17.5](../SPEC.md#175-observability)) — reports, never repairs.
- Dependency audit (`pip-audit`, `npm audit`) in CI.

**Seed data ([§11.4](../SPEC.md#114-cold-start-and-the-catalogue-floor))**
- **The item list is supplied by the product owner** ([Q9](../DECISIONS.md)), not written by an implementation agent. It is already committed at [`seed/items.txt`](../../seed/items.txt) — **100 items, validated against [§12.3](../SPEC.md#123-structural-validation) with zero failures, zero duplicates and zero slug collisions** ([`seed/README.md`](../../seed/README.md) has the analysis). This milestone builds the loader, the warm-up and the marking; it does not invent content.
- **Sizing check before launch** ([§11.4](../SPEC.md#114-cold-start-and-the-catalogue-floor)): at least 50 items, 150–300 preferred. The supplied 100 items give 4,950 pairs — roughly 412 sessions before an actor repeats one — so **the default cooldowns are safe as they stand**. Still compute and log the derived values at boot, because that stops being true if the catalogue is ever trimmed.
- **The 8-domain rule does not apply as written.** Every seed item is an everyday micro-experience, so by subject this is one domain. The rule exists to prevent *sensible* matchups, and the axis this catalogue varies on is valence: 28% pleasant, 47% unpleasant, 25% neutral, leaving ~74% of pairs genuinely contested. Do not "fix" the diversity by padding the list with unrelated nouns without deciding that as a product change first.
- Loader: creates items under a system user, `APPROVED`, `source='seed'`, idempotent.
- A warm-up run that plays synthetic battles so the day-one leaderboard is not N items at exactly 100.00 — and, under Glicko, so that enough items cross the `RANKED_RD` threshold for `/rankings` to be non-empty on launch day. Synthetic battles are marked `source='seed'` and excluded from analytics.

**Operations**
- Sentry on backend and frontend; Prometheus `/metrics`; the alert set from [§17.5](../SPEC.md#175-observability).
- `docs/RUNBOOK.md`: deploy, rollback, restore-from-backup (with a **measured** RTO from a rehearsed restore), what to do when the moderation provider is down, when deadlocks appear, when the sweeper stops, when the outbox backs up, and how to investigate a suspected rating-manipulation report.
- Production environment, DNS, TLS, CDN, managed Postgres with PITR, staging with `Disallow: /`.
- Legal pages: Terms; Privacy — naming the moderation and email providers, describing what a guest's session cookie stores, and **stating the deletion rule in a sentence a person can read** ([§13.7](../SPEC.md#137-account-deletion-and-the-audit-trail)): *"If you delete your account we erase everything that identifies you. The picks you made stay part of the rankings, with nothing linking them to you."* **This sentence is a launch blocker.** Plus an About page explaining the game in three sentences without mentioning mathematics — and answering *"Why 64 characters?"* with *"That's why."*

**Load testing ([§16.6](../SPEC.md#166-load-testing))**
- 500 concurrent players sustained; p95 `pick` < 200ms; zero deadlocks; zero constraint violations.
- Post-run verification: recount `rating_events` against `battles` and every denormalised counter — **zero discrepancies**.

## Database changes

`analytics_events`, `daily_metrics`, and the metric views. No changes to any core table.

## API changes

`POST /api/events`. Admin metrics view. Nothing else.

## Frontend changes

The analytics client (batched, `sendBeacon`, respects Do Not Track), About/Terms/Privacy pages, a 404 and a 500 page in the product's voice.

## Tests

- Every metric view returns correct values against a hand-built fixture dataset with known answers (including the session-gap boundary at exactly 30 minutes, on both sides).
- The session view and the funnel agree on totals — a test that catches the classic "two dashboards, two numbers" failure.
- Event ingest rejects PII-shaped payloads, oversized batches and unknown event names.
- Security headers present on every response; CSP blocks an injected inline script (asserted in a browser test).
- Reconciliation detects a deliberately corrupted counter and **reports without repairing**.
- Seed loading is idempotent — running it twice creates no duplicates.
- Load test passes its thresholds and its post-run integrity recount.
- A restore-from-backup rehearsal succeeds and its RTO is recorded in the runbook.
- Robots and `X-Robots-Tag` on staging verified in CI ([§14.8](../SPEC.md#148-robotstxt)).

## Acceptance criteria

1. The north-star metrics (picks per session, D1/D7 return) are visible on a dashboard and computed from `battles`.
2. All metric definitions live in `docs/analytics.md` and are implemented exactly once each.
3. The load test passes with zero integrity discrepancies afterwards.
4. Every [§13](../SPEC.md#13-security-and-anti-abuse) control is implemented and evidenced in the security review.
5. The supplied seed items are live with a warmed-up, non-uniform leaderboard, and `/rankings` is non-empty on launch day. The derived cooldown values are logged at boot and match the actual catalogue size.
6. Alerting fires correctly for each of: a deadlock, a rating clamp, a stopped sweeper, an open moderation circuit, and a backed-up outbox — each verified by deliberately triggering it.
7. `docs/RUNBOOK.md` is complete, and the restore has actually been rehearsed with a measured RTO.
8. Staging cannot be indexed.
10. The guest-exclusion rating recompute runs successfully against production-shaped data and its output is archived as the baseline.
9. Search Console is verified and the sitemap is submitted.

## Non-goals

A/B testing infrastructure, cohort analysis tooling, marketing site, email digests or re-engagement campaigns, push notifications, referral mechanics, ads, a data warehouse, auto-blocking of suspected abusers, admin tooling beyond the moderation queue, any Phase 2–5 feature.
