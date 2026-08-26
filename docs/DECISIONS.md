# PickOne — decisions

The nine questions the specification deferred, and how they were answered. Each entry records the decision, the reasoning, and **what it changed in the spec** — so a reviewer can tell whether the implementation still matches the intent.

---

## Q1 — Can logged-out visitors play? → **Yes. Guests are first-class.**

**Decision.** An anonymous visitor picks immediately, with no account. A guest is a real `users` row (`is_guest = true`) behind a signed httpOnly session cookie. Registering converts that row **in place** — same `user_id`, same battles, same history.

**Why this is the right call and not just the popular one.** The registration wall was aimed at rating manipulation, but it barely addresses it: *a user cannot choose which pair they are shown*. Sybil identities therefore buy you more **random** votes, not targeted ones, which is a far weaker attack than it appears. Meanwhile the wall was doing real damage — every visitor arriving from a comparison page in search results was asked for an email before they could do the one thing the page invited. That is a direct tax on the SEO strategy the whole of M6 exists to build.

**What it changed:**
- `User` is redefined as *an actor that can pick*, not *a person with an account* ([§6.1](SPEC.md#61-entities)). Guests and members are the same entity in two states, so no invariant needs an `is_guest` branch.
- Guest creation is lazy — first `GET /api/battles/current`, nowhere else ([§4.0](SPEC.md#40-the-first-pick--no-account-required)).
- New [§13.6](SPEC.md#136-guest-play-and-anti-abuse): per-IP guest-creation limits, a janitor that reaps guests with zero completed battles after 7 days, and a **reversibility escape hatch** — because `rating_events` is complete and append-only, ratings can be recomputed over registered users only if guest picks ever prove toxic.
- Every core metric is segmented by `is_guest`, including a **guest-vs-registered agreement** metric with a 5pp alarm threshold ([§15.3](SPEC.md#153-the-metrics-that-matter)). The decision gets evaluated with data, not vibes.
- The funnel target changed shape: *registration → first pick ≥ 80%* became **landing → first pick ≥ 35%, in under 15 seconds**.
- Three gates remain, and they are the only places code may branch on guest-ness: **adding an item, reporting an item, deleting an account.**

**Rejected alternative:** a separate `guest_sessions` table with a nullable `battles.guest_id`. It doubles every constraint, query and test to model something that is already a `User`.

---

## Q2 — Elo or Glicko instead of EGF? → **Yes: three candidates, decided by simulation. Glicko-1 recommended.**

**Decision.** [§10](SPEC.md#10-rating-system) was rewritten. Three systems now sit behind one `RatingSystem` protocol — **Glicko-1 incremental (recommended)**, **Elo with a battle-count K-schedule**, and the **EGF adaptation** (retained as baseline so the original instruction is tested rather than argued away). M3 picks the winner against eight gates.

**Why EGF turned out to be the weakest fit.** Two findings drove this:

1. **EGF is Bradley–Terry under a coordinate change.** `win_prob` collapses to `1 / (1 + ((C−r₁)/(C−r₂))^B)` — only the ratio of distances from `C` matters. `C` is not a quality ceiling, it is the singularity of the reparameterisation.
2. **Every distinctive EGF feature solves a Go problem PickOne does not have.** The `C = 3300` reparameterisation calibrates the scale to *handicap stones* — there are none here. The rating-dependent `con(r)` proxies "stronger players have better-established ratings" — in PickOne, rating level and certainty are unrelated. The `bonus` term counteracts deflation from *improving* juniors — PickOne's new items never improve and never retire, so it is a pump with no sink.

**And the real mismatch:** PickOne's hard problem is not *how strong is this item* but **how sure are we?** Battle counts are heavily skewed — some items have 3 battles, some have 3,000. EGF has no representation of certainty. Glicko's entire contribution is exactly that representation.

**Why Glicko-1 rather than Glicko-2.** Glicko-2 adds a volatility term modelling a competitor whose *true strength changes over time*. **An item's quality does not change** — Carbonara is exactly as good next month. Glicko-2's headline feature models something that does not happen here, while adding an iterative root-find to the hottest transaction in the system. That is the overengineered option, and it is refused for a reason rather than for taste. ([§10.3](SPEC.md#103-what-glicko-2-would-add-and-why-it-is-the-overengineered-choice))

**Glicko-1 is a net *reduction* in complexity** versus the EGF adaptation. It deletes the ceiling, the singularity, the clamp, `bonus`, the inflation pump, the provisional-K hack and the `RANKINGS_MIN_BATTLES` guess — RD replaces the last of these with a derived threshold ([§10.5](SPEC.md#105-ranked-and-unranked--what-rd-buys-the-product)).

**What it changed:**
- `Rating` is `(value, deviation)` everywhere, for every system. `items.rating_deviation`, plus RD snapshots on `battles` and `rating_events`, exist from the first migration — **this is what makes the system swappable without a migration on the largest table.**
- `rating_events.terms` (JSONB) holds the system-specific intermediates, so the audit trail survives a system change.
- Gates were restated system-agnostically, and two were added: **`GATE-R7` calibration** (predicted vs observed win rates within 3pp per decile — the gate that tells you whether the system is *right* rather than merely stable) and **`GATE-R8` leaderboard integrity**. Scenario **S8** (duplicate items) was added as a Phase 3 pre-check.
- New concept: **ranked vs unranked**. An item joins the leaderboard when `RD < 100` (~10–20 battles); until then its page says *"Still settling. 7 picks in."*

**Two honest caveats, both in the spec.** Glicko assumes rating periods of 10–15 games and we apply it per battle — the standard incremental approximation, bounded by `RD_MIN` and measured by `GATE-R7`. Batch periods are rejected on **product** grounds: the pick response shows a rating delta immediately, and batching would make that impossible.

**Negative ratings fall out of this**, and [Q10](#q10--should-everything-start-at-0--yes-this-is-the-best-change-in-the-round) turns them from a wart into the point.

---

## Q3 — Next.js? → **Confirmed.**

No change. [§17.2](SPEC.md#172-the-frontend-decision-honestly) keeps the honest argument for the Jinja + htmx alternative on the record, because the reasoning matters if the team shape changes later.

---

## Q4 — Item length? → **64 characters.**

**Decision.** `2–64` after normalisation. The counter appears at 48 as a nudge, not a wall — past roughly 48 an item reads as a sentence rather than a thing.

**And the answer to "why 64?" is in the spec, verbatim, as product copy** ([§12.3](SPEC.md#123-structural-validation)):

> **Why 64 characters?**
> That's why.

It appears in the About page, in the counter's tooltip, and in support replies. It is exactly the right register for this product: terse, deadpan, and refusing to explain itself. `[P3]`

**One engineering note:** the limit can be *raised* later painlessly but can never be *lowered* without orphaning existing items. 64 is a ceiling, not a starting point.

---

## Q5 — Does Skip need a qualifier? → **No. Report comes later, and not for pairs.**

**Decision.** Skip stays one unqualified action. Item reporting ships in MVP (it is the abuse mechanism); **pair** and **near-duplicate** reporting is future work.

**What it changed** ([§12.6](SPEC.md#126-admin-review)): reporting is available only from an item page, **never from inside the loop** — a report button next to the cards is a second primary verb and a way to avoid deciding. `[P1]` `[P2]`

Until pair reporting exists, both signals are **inferred at zero UI cost** from data the loop already produces:
- A comparison with a high `skip_count / battle_count` is a bad pair.
- An item with a high skip rate across many *different* opponents is a bad item, and goes to the review queue automatically.
- Near-duplicates produce near-identical rating trajectories plus a ~50/50 comparison with a high skip rate — which is precisely what Phase 3's candidate generation will consume, and why simulation scenario **S8** exists.

All three are SQL over `battles` and `comparisons`. They can ship as admin-queue feeds whenever they earn it.

---

## Q6 — Are the indexing thresholds right? → **Doesn't matter yet. Launch conservative.**

`ITEM_INDEX_MIN_BATTLES = 5`, `COMPARISON_INDEX_MIN_BATTLES = 10`, both config. Tune against Search Console using **organic sessions per indexed page**, and not for at least six weeks — there will not be enough data before then. Starting tight and loosening is cheap; recovering from a thin-content demotion is not.

---

## Q7 — Is a `GET` that creates a battle acceptable? → **Your reframe is better. Adopted.**

**Decision.** The invariant is now stated as: **every actor always has exactly one standing pair waiting for them, unless their catalogue is exhausted** ([§9.3](SPEC.md#93-the-standing-pair-invariant)).

Under that framing `GET /api/battles/current` is what it appears to be — **a read of a resource guaranteed to exist** — and creation is an implementation detail of maintaining the invariant, performed lazily on read, exactly as a cache populates itself. The smell goes away for a real reason rather than by relabelling.

**And it is not overengineering, because it is the same code.** No background job pre-creates pairs for idle actors — *that* would be overengineering, and with guest play it would mean a pending battle for every crawler-created row. The invariant is maintained lazily, at the moment somebody looks. What you gain is that "the pair is always there" is now the stated rule, so the endpoint's shape follows from the model instead of needing a footnote defending it.

The one case the invariant genuinely cannot hold is catalogue exhaustion, which returns `503` — the honest answer, and a signal to add items.

**Still flagged:** re-open this the moment the standing pair gains a cost (a rate-limit charge, a notification, a paid resource). Then it becomes `POST /api/battles` with the `GET` retained as a pure read.

---

## Q8 — Account deletion → **Delete the person. Keep the picks.**

**Decision.** Implemented literally, in [§13.7](SPEC.md#137-account-deletion-and-the-audit-trail):

- **Destroyed:** email, password hash, sessions, tokens, settings, and the `users` row itself.
- **Preserved:** every `battles` row (with `user_id = NULL`), every `rating_events` row, every rating, every counter.

**The `users` row is deleted outright, not anonymised in place.** A surviving row with a stable id still links every action to one identity and is still pseudonymous personal data — that is not "removing all their personal information".

**Why the picks stay:** a rating is the collective output of everyone who ever played. Removing one person's contributions would retroactively rewrite a public artefact that other people's picks were measured against. The battles go stale — unattributable, ungroupable, useless for per-user analytics — but they never stop counting.

**What it changed:**
- `battles.user_id` became **nullable** with `ON DELETE SET NULL`, and the partial unique index gained `AND user_id IS NOT NULL`.
- `item_reports.reporter_user_id` became `SET NULL` rather than `CASCADE` — otherwise deleting an account could **un-hide a reported item**.
- Analytics views must tolerate `user_id IS NULL`; the reconciliation job must not read a NULL actor as corruption. Both are tested.
- Guests get the same treatment on reaping.
- **A launch blocker:** the privacy policy must say this in a sentence a person can read. *"If you delete your account we erase everything that identifies you. The picks you made stay part of the rankings, with nothing linking them to you."*

---

## Q9 — Who curates the seed items? → **You do.**

M7 provides the loader, the warm-up run and the `source = 'seed'` marking; the list is yours.

**One thing worth knowing before you write it** ([§11.4](SPEC.md#114-cold-start-and-the-catalogue-floor)): you said "several", and the binding constraint is not arithmetic but comedy. With `N` items there are `N(N−1)/2` pairs, but `USER_RECENT_ITEMS = 8` means a catalogue of 20 leaves only 12 items to draw from and feels repetitive within minutes.

**At least 50 to launch; 150–300 preferred; at least 8 domains with no domain above 20%.** Sixty items spread across food, weather, chores, days, sensations, objects, places and abstractions produce far funnier pairs than three hundred foods — a catalogue that is 80% one domain generates *sensible* matchups, and sensible matchups are the failure mode. `[P6]`

If the launch list is short, drop `USER_PAIR_COOLDOWN_DAYS` and `USER_RECENT_ITEMS` proportionally and raise them as the catalogue grows. M7 sets both from the actual seed count rather than from the defaults.


---

## Q10 — Should everything start at 0? → **Yes. This is the best change in the round.**

**Decision.** `INITIAL_RATING = 0`. Every item starts at zero, ratings are always rendered with an explicit sign, and **the sign carries the meaning**:

```
Carbonara            +487
Rain                  +31
Monday                −18
Doing taxes          −312
Fitting bed sheets   −406
```

**Why this is better than the 100 I had recommended.** I had treated negative ratings as a consequence to accept. That was the wrong frame. Under a conserving system, roughly half the catalogue ends up below the starting value *whatever that value is* — so the only question is whether being below it means anything. At 100, negative meant "worse than average by more than 100 points", an arbitrary threshold with no interpretation. At 0, negative means **below average**, which is a fact. The negatives stop needing an excuse and become the most legible thing on the page.

Three further arguments, in descending order of how much they should convince you:

1. **It is free.** Elo and Glicko are **translation-invariant** — the origin is a label, and moving it changes no dynamics, no convergence, no calibration, no matchmaking. One config value.
2. **`100` invites a misreading that `0` does not.** A hundred reads as a full score, a percentage, or a maximum — so an item at `2,481` looks like a bug and an item at `100` looks perfect rather than untested. Zero has no such collision, and the *"still settling"* state ([§10.5](SPEC.md#105-ranked-and-unranked--what-rd-buys-the-product)) already covers "we don't know yet", so `0` never has to double as "no data".
3. **It is one more strike against the EGF candidate.** EGF is *not* translation-invariant: `con(r)` and `beta(r)` reference absolute distance from `C`, and `R_FLOOR = 0` would clamp every item at its own starting value. Choosing it now also means re-anchoring `C`, `R_BONUS` and `R_FLOOR`. The two systems worth choosing take this change for free; the one that resists it was already ranked last.

**What I checked before agreeing.** A rough Elo simulation — 300 items, 300,000 battles, continuous arrivals at 0 — held the population mean at **exactly 0.0**, with a spread of roughly −730 to +900 (comfortably clearing `GATE-R4`) and **~93% sign agreement** between an item's rating sign and the sign of its `wins − losses` under the specified 50/35/15 matchmaking mix.

**What that check also did was contradict me.** I had written that raising the `RANDOM` weight would raise sign agreement, on the reasoning that neighbourhood matching compresses records toward 50%. It did not: a random-heavy mix scored slightly *lower*, and neighbourhood-only scored about the same. The differences sit inside single-seed noise, so the claim is simply unsupported — the spec now says the relationship must be **measured across mixes by the real harness**, not predicted.

**What it changed:**
- New **`GATE-R9` (sign agreement)**, reported as a percentage at three or more matchmaking mixes. Above 85%, product copy may say *"people pick it more often than not"*; below it, copy must say *"above average"*, which is always exactly true. **The simulation chooses the product's vocabulary** ([§10.6](SPEC.md#106-simulation--the-decision-procedure)).
- Display rules ([§10.4](SPEC.md#104-zero-is-the-origin-and-the-sign-is-the-product)): always signed, real U+2212 minus, never colour as the only encoding, no animation or fanfare on a sign flip (an item near zero genuinely is a coin flip and the UI must not dramatise it).
- `items.rating` now defaults to `0.0000`.
- **A new invariant, because this decision introduces a real footgun:** `if item.rating:` is `False` at exactly zero, which is now both legal *and* meaningful. Truthiness tests on ratings are banned by lint in `rating/`, `battles/` and `public/`, and M6 carries an explicit regression test that an item at `0` renders as `0` — in the page, the `<title>`, the meta description and the OG image — and never as blank, missing, or "unrated".
