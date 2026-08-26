# PickOne — product specification

> PickOne lets you choose between anything, and everyone's choices create the world's ranking of everything.

This directory is the complete, implementation-ready specification for PickOne's MVP, plus the phased roadmap beyond it. **No product code has been written.**

## What's here

| File | What it is |
|---|---|
| **[SPEC.md](SPEC.md)** | The reference specification. Sections 1–21: product, domain model, database, API, battle state machine, rating system, matchmaking, moderation, security, SEO, analytics, testing, architecture, roadmap, anti-patterns, handoff. |
| **[DECISIONS.md](DECISIONS.md)** | The nine deferred product decisions — **all now answered**, with the reasoning and what each one changed in the spec. |
| **[milestones/](milestones/)** | Eight self-contained implementation briefs, one per milestone. |

## The milestones

```
M0 Foundations
   └─► M1 Auth ──┬─► M2 Items & moderation ──┐
                 │                            ├─► M4 Battles ──► M5 Game UI ──┐
                 └────────────────────────────┤                               ├─► M7 Launch
        M3 Rating systems (parallel, no deps) ─┘                M6 SEO pages ──┘
```

| Brief | Goal |
|---|---|
| [M0 — Foundations](milestones/M0-foundations.md) | Running skeleton, config register, real-Postgres test harness, CI |
| [M1 — Auth](milestones/M1-auth.md) | Actors: guests, registration-as-conversion, verify, login, reset, hard delete |
| [M2 — Items & moderation](milestones/M2-items-moderation.md) | Add one → normalise → dedupe → moderate → publish at rating 100 |
| [M3 — Rating systems](milestones/M3-rating-engine.md) | Glicko-1 / Elo / EGF behind one protocol + simulator. **Produces the launch system decision** |
| [M4 — Battles](milestones/M4-battles.md) | **The hard one.** Comparisons, matchmaking, the two atomic transactions |
| [M5 — Game UI](milestones/M5-game-ui.md) | The screen that is the product — playable with no account |
| [M6 — SEO pages](milestones/M6-seo.md) | Rankings, item pages, comparison pages, sitemaps, thresholds |
| [M7 — Launch](milestones/M7-launch.md) | Analytics, hardening, seed content, load test, runbook |

## Reading order

- **Deciding whether to build it:** §1, §2, §3, then [DECISIONS.md](DECISIONS.md).
- **Implementing:** §21 (handoff + invariant card), then your milestone brief, then the spec sections it references.
- **Reviewing someone's implementation:** §21.2 (the invariant card) and §20 (what to avoid).

## Decisions already made

All nine open questions are answered in [DECISIONS.md](DECISIONS.md). The four that changed the architecture:

- **Guests can play.** No account before the first pick. A guest is an ordinary `User` row with `is_guest = true`, so every invariant holds unchanged and registration converts the row in place.
- **The rating system is chosen by simulation across three candidates** — Glicko-1 (recommended), Elo with a K-schedule, EGF-adapted — behind one `RatingSystem` protocol. Ratings are `(value, deviation)` from day one.
- **Everything starts at 0, and the sign means something.** `Carbonara +487`, `Doing taxes −312`. Positive is above average; negative is below. Free under Glicko/Elo, which are translation-invariant.
- **Next.js**, confirmed.
- **Deleting an account deletes the person and keeps the picks.** The `users` row goes; `battles.user_id` becomes `NULL`; every rating and counter is untouched.

Two things still need a human, not an agent:

1. **The seed item list** — you're curating it ([§11.4](SPEC.md#114-cold-start-and-the-catalogue-floor) has the size and diversity floor).
2. **The privacy-policy sentence about deletion** ([§13.7](SPEC.md#137-account-deletion-and-the-audit-trail)) — a launch blocker.
