# PickOne — Product & Technical Specification

**Status:** v1.0 — approved for implementation handoff
**Scope:** MVP specification + phased roadmap
**Audience:** implementation agents, one milestone at a time

> PickOne lets you choose between anything, and everyone's choices create the world's ranking of everything.

**How to read this document**

- Sections 1–20 are the *reference spec*. They define what is true about the product and the system. (Technical architecture is §17, inserted before the plan; the requested "implementation plan / roadmap / what to avoid / handoff" sections are §18–§21.)
- Section 21 and [`milestones/`](milestones/) are the *handoff*. Each milestone is a self-contained brief a coding agent can execute without reading the whole spec (though it should).
- [`DECISIONS.md`](DECISIONS.md) records the nine product decisions that were deferred and have now been answered, with the reasoning behind each.
- Anything marked **`[CONFIG]`** is a tunable constant, not a hard-coded value.
- Anything marked **`[INVARIANT]`** must never be violated. These are the load-bearing walls.

---

## 1. Executive product summary

PickOne is a pairwise choice game. A user is shown two arbitrary, usually unrelated things and picks one. That single tap resolves a *battle*, updates the rating of both items, and immediately produces the next pair.

```
SEE TWO THINGS  →  PICK ONE  →  NEXT ONE  →  (forever)
```

The absurdity is the product. "Carbonara vs Fitting bed sheets" is not a category error to be designed away — it is the reason the loop is funny and the reason people keep tapping. Every pick is a vote in a single, global, continuously-evolving ranking of everything.

Two things fall out of the loop for free, and both are the growth engine:

1. **A ranking of everything.** Public, global, always changing.
2. **A permanent public page for every pair that has ever been compared.** `Carbonara vs Pizza — 8,421 battles, 61% / 39%`. These pages are the SEO surface, and they get better the more the game is played.

The business model is attention: the loop is the retention mechanism, the public pages are the acquisition mechanism, and ads (Phase 5) are the monetisation — placed everywhere *except* the loop.

**MVP in one paragraph.** A user registers with email and password, verifies, and lands on a screen with two large cards. They tap one. The server — never the client — decided which two items to show, gave the battle a short lifetime, and is the only party that can record a result. Ratings move using a configurable adaptation of the EGF rating system. Users can add their own items in plain text, which pass automatic moderation before entering circulation. A public rankings page, public item pages, and public comparison pages are server-rendered, indexable, and gated behind data thresholds so the site never floods the index with empty pages.

---

## 2. Product principles

These are the tie-breakers. When a decision is ambiguous, the principle wins.

**P1 — One verb.** The product has exactly one primary action: *pick one*. Everything else is secondary chrome. If a feature adds a second primary verb, it is not MVP.

**P2 — The loop is sacred.** Nothing may be inserted between PICK and NEXT: no interstitial, no modal, no navigation, no ad, no confirmation, no "are you sure". Feedback after a pick is measured in hundreds of milliseconds, not screens.

**P3 — The user never does mathematics.** Ratings, expected scores, K-factors and probabilities exist in the database and never in the user's head. The word "rating" may appear as a number on a leaderboard. The words *score*, *evaluate*, *rate*, *review*, *submit*, *pairwise comparison*, *vote* never appear in the UI.

**P4 — No priming.** Ratings, ranks, win rates and battle counts are **never** visible before a choice. Showing them turns a gut reaction into a popularity guess and poisons the dataset. Reveal after, never before.

**P5 — The server owns the truth.** The client cannot invent a battle, cannot choose the pair, cannot decide who won beyond naming one of two server-supplied ids, and cannot make anything happen twice. Every rule is enforced by the database, not by a Python `if`.

**P6 — Absurdity is a feature.** Matchmaking must never converge on "sensible" or "fair" matchups. A deliberate share of pairs is pure random. Do not fix the comparison of unrelated things — it is the product.

**P7 — Boring infrastructure.** PostgreSQL, one API, one worker, one frontend. No Redis, no Kafka, no microservices, no ML training at MVP. Every piece of infrastructure must be justified by a problem that already exists.

**P8 — SEO is a product surface, not a checklist.** Public pages are real pages with real content for real people. If a page would not be useful to a human, it must not be indexable.

**P9 — Design for Phase 2–5, build only MVP.** The domain model must not close doors (demographics, item merging, translation, pairwise consensus on things other than items). No Phase 2–5 code ships in MVP.

---

## 3. MVP scope

### 3.1 Must have

| # | Capability | Definition of done |
|---|---|---|
| 0 | **Guest play** | An anonymous visitor can pick immediately, with no account. A guest is a real `users` row (`is_guest = true`) behind a signed httpOnly cookie, so every invariant below holds unchanged. Registering converts the guest in place and keeps their history. |
| 1 | **Accounts** | Email/password registration, email verification, login, logout, password reset. Argon2id hashing. Server-side sessions in an httpOnly cookie. Required to **add** an item; never required to **pick** one. |
| 2 | **Items** | Authenticated + verified user creates a plain-text item. Normalised, deduplicated, moderated automatically. Approved items start at rating **0** `[CONFIG: INITIAL_RATING]` — see [§10.4](#104-zero-is-the-origin-and-the-sign-is-the-product). |
| 3 | **Battles** | Server selects two items, creates a battle, returns a battle id. Client can only name a winner from the two supplied items. |
| 4 | **One pending battle per actor** | Every actor (guest or registered) always has exactly one live pending battle, unless their catalogue is exhausted. Enforced by a partial unique index. Refreshes, double clicks, extra tabs and retries all observe the *same* battle. See [§9.3](#93-the-standing-pair-invariant). |
| 5 | **Expiration** | `expires_at = created_at + 60s` `[CONFIG: BATTLE_TTL_SECONDS]`, strictly under one minute. Expired battles change no ratings. Next request creates a fresh matchup. |
| 6 | **Skip** | First-class action. No rating change. Recorded permanently for analytics and future matchmaking. |
| 7 | **Result submission** | `POST` referencing the server battle id with only `winner_id`. Server verifies ownership, membership, pending status and expiry. Exactly-once rating application. |
| 8 | **Rating** | One of three candidate systems — **Glicko-1 (recommended)**, Elo with a K-schedule, or the EGF adaptation — behind a single `RatingSystem` protocol. Chosen by simulation against nine gates before launch. Every item starts at **0**, and the sign of a rating is meaningful `[CONFIG: INITIAL_RATING]`. See [§10](#10-rating-system). |
| 9 | **Matchmaking** | A separate module from rating. Mixed strategy: rating-neighbourhood, pure random, and cold-start boost. Proportions configurable, with a floor on randomness. |
| 10 | **Global rankings** | Public page. Rating, wins, losses, battle count. Paginated. |
| 11 | **SEO** | Server-rendered `/`, `/rankings`, `/item/{slug}`, `/compare/{a}-vs-{b}`. Metadata, canonicals, Open Graph, sitemap, robots, structured data, indexing thresholds. |
| 12 | **Moderation** | Pretrained moderation service behind an interface. `APPROVED / REVIEW / REJECTED`. Minimal admin review queue. |
| 13 | **Anti-abuse** | Rate limiting on every mutating endpoint, verification gates for creation, guest-specific controls ([§13.6](#136-guest-play-and-anti-abuse)), auditability of every rating change. |
| 14 | **Analytics** | Core-loop funnel measured from the database, not the client. |

### 3.2 Explicitly excluded from MVP

Not "later in MVP" — **absent**.

- Social login / OAuth providers
- Images, emoji-rich items, links, rich text, categories, tags
- Item editing or renaming by users (**items are immutable in MVP** — see §14.9)
- Comments, likes, follows, profiles-as-pages, user-to-user anything
- User ratings / player skill / weighted voters
- Demographic rankings, country/age/gender (Phase 2)
- Similar-item detection and merging (Phase 3)
- Translations, localisation, hreflang (Phase 4)
- Ads (Phase 5)
- Native mobile apps, push notifications
- Search / autocomplete over items
- Leaderboards of users, streaks, XP, achievements, gamification layers
- Public API, API keys, data export
- A/B testing framework
- Reporting a *pair* or a *near-duplicate* (item reporting ships in MVP; pair and similar-item reporting is future — [§19](#19-future-roadmap))
- Any qualifier on Skip ("no opinion" vs "bad pair") — see [DECISIONS.md Q5](DECISIONS.md)
- Glicko-2 volatility — [§10.3](#103-what-glicko-2-would-add-and-why-it-is-the-overengineered-choice)

---

## 4. User flows

Notation: `→` is a screen transition, `⟳` is an in-place update with no navigation.

### 4.0 The first pick — no account required

`[INVARIANT]` **Nothing stands between a stranger and their first pick.** This is the single most important flow in the product, because it is also the landing experience for every visitor arriving from a comparison page in search results.

```
stranger lands on / or /compare/carbonara-vs-pizza
  → clicks a card, or "Pick one yourself"
  → /play  (client component mounts)
  → GET /api/battles/current                     ← no session cookie present
      server: create users row (is_guest = true, no email, no password)
              issue session cookie exactly as for a registered user
              create the battle
      200 { battle_id, expires_at, items: [...] } + Set-Cookie: po_session=...
  → cards render, user picks
  → loop continues indefinitely, with real ratings moving
```

A guest is **a real `users` row**, not a special case. Every invariant in this document is expressed in terms of `user_id`, so the partial unique index, both battle transactions, `rating_events`, the reconciliation job and every analytics view work unchanged. The only differences are `is_guest = true`, a null email, and the controls in [§13.6](#136-guest-play-and-anti-abuse).

**Guest creation is lazy and cheap.** A guest row is created on the first `GET /api/battles/current` and nowhere else — never on a page view, never on `/`, never by rendering a public page. Cost is ~100 bytes; a janitor job ([§13.6](#136-guest-play-and-anti-abuse)) reaps guests that never completed a battle.

**What a guest cannot do:** add an item (requires a verified account), report an item, or delete their account. The nav shows `Log in` and, once they have picked `[CONFIG: GUEST_PROMPT_AFTER_PICKS = 25]` times, one dismissible line above the cards — *"Keep your picks. Make an account."* — which never blocks the loop and never becomes a modal. `[P2]`

### 4.1 Registration and guest conversion

```
guest (or stranger) → "+ Add one", "Log in", or the keep-your-picks line
  → /register
      email, password
      → POST /api/auth/register  (201)
        ├─ session cookie belongs to a guest  → CONVERT that row in place:
        │     set email, password_hash, is_guest = false. Same user_id.
        │     Every battle, every rating contribution, every session is preserved.
        └─ no session                          → create a fresh registered user
      → "Check your inbox."  (already logged in, unverified)
  → email link → /verify?token=... → POST /api/auth/verify → "You're in." → /play
```

Design notes:

- **Conversion is an `UPDATE`, never a copy-and-merge.** Same primary key, so nothing referencing `user_id` has to move. This is the payoff for modelling guests as ordinary users, and it is why a guest who has played 200 battles loses nothing by signing up.
- **A registered user's session is never converted back to a guest.** Logging out clears the cookie; the next `GET /api/battles/current` issues a fresh guest.
- **The user is logged in immediately after registration**, before verification. Verification gates item creation, not picking.
- **Registering with an email that already exists while holding a guest session** → `409 email_taken`. Do **not** silently merge two identities; ask them to log in. On login, the guest row is left behind and reaped by the janitor. Merging picks across identities is a Phase-something problem and a bad idea to improvise.
- Password reset: `/forgot` → always `202` (no enumeration) → `/reset?token=` → new password → all sessions for that user revoked → `/play`.

### 4.2 First battle

```
/play  (client component mounts)
  → GET /api/battles/current
      200 { battle_id, expires_at, server_time,
            items: [ {id, text, slug}, {id, text, slug} ] }
      ← NO ratings, NO ranks, NO battle counts in this payload  [P4]
  → two cards render
  → first-run only: a single ghost line under the cards, "Tap one. That's it."
      (dismissed forever on first pick; never shown again)
```

### 4.3 The repeated loop

This is the whole product. One network request per pick.

```
cards visible
  → user taps left card
  ⟳ card lifts / other card recedes            (~120ms, starts optimistically before response)
  → POST /api/battles/{id}/pick { winner_id }
      200 {
            result: { winner_id, items: [ {id, rating_before, rating_after, delta}, ... ],
                      crowd: { winner_share: 0.61, battle_count: 8421 } },
            next:   { battle_id, expires_at, items: [...] }
          }
  ⟳ reveal for [CONFIG: RESULT_REVEAL_MS = 900]:
        winner card highlighted
        "61% agree"   (only if comparison.battle_count >= 20, else omitted)
        ratings shown as small deltas               [P4 — after, never before]
  ⟳ cards cross-fade to the `next` pair
  → loop
```

**Why the response embeds `next`:** the one-pending-battle invariant means the next battle *cannot* exist until this one resolves, so it cannot be prefetched. Returning it in the same response makes the loop a single round trip and lets the card swap be instant. If `next` is absent (creation failed, no eligible pair), the client falls back to `GET /api/battles/current`.

**Expiry during the loop.** A battle older than 60s is gone. Two cases:

- *Client notices first:* a timer at `expires_at` silently requests a fresh battle and cross-fades the cards. No banner, no error, no explanation. In a loop where the median decision is ~3 seconds, this is rare.
- *Server notices first:* the pick returns `410 battle_expired`. The client discards it, fetches a new battle, and shows a single quiet line for 1.5s: *"That one timed out."* Never a modal, never a red error.

### 4.4 Skip

```
cards visible
  → user presses [ Skip ] / spacebar / swipes down
  → POST /api/battles/{id}/skip
      200 { battle: { status: "SKIPPED" }, next: { ... } }
  ⟳ both cards slide away together (~150ms), next pair fades in
```

Skip is deliberately as fast and as easy as picking. It is not a failure state and it is not discouraged. A high skip rate on a specific item is a **signal**, not a problem — it feeds Phase 3 quality work and can flag moderation misses.

### 4.5 Add one

```
nav: "+ Add one"  →  /add
      (guest or logged out → /register first; this is the ONLY gate in the product)
      "What should we add?"
      [ ______________________ ]      (2–64 chars, live counter appears at 48)
                [ Add one ]
  → POST /api/items { text }
      201 { item, status: "APPROVED" }   → "Added."   → 800ms → /play with the new item
                                                          in the very next battle  [see note]
      202 { item, status: "REVIEW"   }   → "Added. We'll take a quick look before it joins."
      409 { existing_item }              → "Already here." + link to /item/{slug}
      422 { code: "rejected" }           → "We can't add that one."   (no detail — see §12.5)
```

**The "straight into a battle" moment** is the payoff for contributing, and it is cheap: after a successful `APPROVED` creation, the redirect to `/play` carries `?seed={item_id}`, and battle creation honours a one-shot seed hint (validated server-side: the item must exist, be approved, and not be the same as the opponent). The seed is consumed once and never persisted.

### 4.6 Ranking discovery

```
nav: "Rankings"  →  /rankings           (server-rendered, page 1)
      #1  CARBONARA         +487   1,204 W / 388 L    1,592 battles
      #2  ...
  → click an item  → /item/carbonara     (server-rendered)
        rating, rank, W/L, battle count
        "Closest rivals"     → links to /compare/...
        "Biggest wins"       → links to /compare/...
        "Recent battles"
  → click a rival  → /compare/carbonara-vs-pizza   (server-rendered)
        8,421 battles · Carbonara 61% · Pizza 39%
        both item cards → links back to /item/...
        [ Pick one yourself ]  → /play
```

Every public page has exactly one call to action, and it is always the same one: **play**.

---

## 5. UI / UX specification

### 5.1 Desktop — the game screen (`/play`)

```
┌──────────────────────────────────────────────────────────────┐
│  PICKONE            Pick One   Rankings   + Add one    ◍ me   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│                   What would you choose?                     │
│                                                              │
│        ┌────────────────────────────────────────┐            │
│        │                                        │            │
│        │              CARBONARA                 │            │
│        │                                        │            │
│        └────────────────────────────────────────┘            │
│                                                              │
│                          VS                                  │
│                                                              │
│        ┌────────────────────────────────────────┐            │
│        │                                        │            │
│        │          FITTING BED SHEETS            │            │
│        │                                        │            │
│        └────────────────────────────────────────┘            │
│                                                              │
│                       [ Skip ]                               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

- Cards are **stacked vertically** on all breakpoints, not side by side. Reasons: identical layout desktop↔mobile (one component, one set of animations), no left/right bias, item text of wildly varying length stays readable, and the vertical stack matches the thumb-reachable mobile shape. `←`/`→` keys still map to top/bottom (see §5.4) because the mental model users bring is "left and right".
- Card sizing: `min-height: clamp(140px, 26vh, 260px)`, `max-width: 720px`, centred. Cards are visually dominant — together they occupy ≥55% of the viewport height.
- Item typography: `clamp(1.75rem, 5.5vw, 3.5rem)`, weight 700, `text-transform: uppercase`, `text-wrap: balance`, line clamp at 3 lines with a font-size step-down for long items. Stored text is never mutated — casing is purely presentational (this matters for Phase 4 languages where uppercase is wrong; the transform must be a themeable token, not baked into the string).
- "VS" is small, muted, non-interactive, `aria-hidden`.
- The header question "What would you choose?" is static and never changes. It is the only instruction in the product.
- Nothing else is on this screen. No sidebar, no stats, no counters, no streak, no ad, no "battles today". `[P2]`

### 5.2 Mobile

Identical layout, tuned:

- Cards fill the width with 16px gutters; the Skip button sits in the bottom third, always within thumb reach, `min-height: 48px`.
- **Tap** is the primary and always-available interaction.
- **Swipe is an optional augmentation, never the only route to any action.** Swipe up on the top card / down on the bottom card picks it; swipe either card horizontally past a threshold also picks it. A short downward two-finger flick or the visible button skips. Swipe is layered on top of buttons — if gesture handling fails, everything still works.
- No pull-to-refresh hijacking. No haptics beyond a single light impact on pick (respect the OS setting).
- Safe-area insets respected; the Skip button never sits under a home indicator.

### 5.3 Animation principles

Total time from tap to the next pair being interactive: **≤ 1.1s**. This is a hard budget, not an aspiration.

| Beat | Duration | Motion |
|---|---|---|
| Press feedback | 80ms | Chosen card scales to 1.02, shadow lifts. Starts **optimistically on pointerdown**, before the request. |
| Loser recedes | 120ms | Opacity → 0.35, scale → 0.98. |
| Result reveal | 900ms `[CONFIG: RESULT_REVEAL_MS]` | Winner card border accent; crowd line and rating deltas fade in over 150ms and hold. |
| Swap | 180ms | Cross-fade + 8px upward drift for the incoming pair. |

Rules:

- Easing: `cubic-bezier(0.2, 0, 0, 1)` for entrances, `cubic-bezier(0.4, 0, 1, 1)` for exits. One shared token set.
- **No layout shift.** Card containers keep fixed geometry across the swap; only content cross-fades. CLS target 0.
- **`prefers-reduced-motion: reduce`** → all transforms and drifts drop to opacity-only cross-fades at 100ms; the reveal hold is unchanged. Nothing becomes unreachable.
- Never animate anything the user did not initiate.
- If the response has not arrived by 400ms, the loser card shows an inline skeleton shimmer — no spinner overlay, no blocking.

### 5.4 Keyboard

MVP ships these (they are trivial and disproportionately loved by power users, who are the ones who produce battle volume):

| Key | Action |
|---|---|
| `←` or `↑` or `1` | Pick the top card |
| `→` or `↓` or `2` | Pick the bottom card |
| `Space` | Skip |
| `Tab` / `Shift+Tab` | Move focus between the two cards and Skip |
| `Enter` / `Space` on a focused card | Pick that card |

`Space` is only "skip" when focus is on the document body, not when a card or button has focus — otherwise it would conflict with native button activation. A single dismissible line on first visit shows the shortcuts.

### 5.5 Navigation

```
PICKONE     Pick One    Rankings    + Add one              [avatar / Log in]
```

Five items. That is the entire navigation for MVP. `+ Add one` is visually distinct (outlined pill), the rest are plain text links. On mobile the nav collapses to the wordmark + `+ Add one` + avatar; `Pick One` and `Rankings` move into the avatar menu. Do not add a hamburger for three links.

Footer (public pages only, not `/play`): About · Rankings · Terms · Privacy · Contact. `/play` has no footer — nothing should suggest scrolling away from the loop.

### 5.6 Copy and terminology

**The lexicon.** These words are the product's voice. Use them exactly.

| Concept | UI says | Never says |
|---|---|---|
| The action | **Pick one** | Vote, Submit, Choose your favourite, Select |
| The prompt | **What would you choose?** | Which is better?, Rate these, Compare |
| Adding | **+ Add one** / **What should we add?** / **Add one** | Add item, Create item, Submit item, New entry |
| Success | **Added.** | Item created successfully, Thanks for your submission |
| Passing | **Skip** | Pass, No opinion, Neither, Can't decide |
| The list | **Rankings** | Leaderboard, Charts, Top rated, Best of |
| A pair page | **Carbonara vs Pizza** | Comparison analysis, Head-to-head report |
| Agreement | **61% agree** | 61% of voters selected this option |
| Timeout | **That one timed out.** | Your session has expired. Error 410. |
| Unranked item | **Still settling. 7 picks in.** | Insufficient data, Provisional rating, Not enough votes |
| A rating | **+487** / **−312** / **0** — always signed | 487, Score: 487, 487 points |
| What the sign means | **people pick it more often than not** (only if `GATE-R9` ≥ 85%, else **above average**) | Positive sentiment score, Net favourability |
| Guest nudge | **Keep your picks. Make an account.** | Sign up to save your progress!, Create a free account today |
| Length limit | **64 characters.** → *"Why 64?"* → **"That's why."** | Maximum length exceeded (64 character limit) |
| Rejection | **We can't add that one.** | Your content violates our community guidelines |

Tone: short, lowercase-friendly, full stops, no exclamation marks, no emoji in system copy, no jokes written *by the product* — the jokes come from the item pairs. Never explain the rating system. Never use the words *rating*, *score* or *algorithm* outside the Rankings page and the About page.

Words that must not appear anywhere in the UI: *submit vote, rate this item, evaluate, review, score, pairwise comparison, Elo, algorithm, engagement, community guidelines*.

### 5.7 Accessibility (WCAG 2.2 AA — a launch requirement, not a follow-up)

- Each card is a real `<button>` with `aria-label="Pick: Carbonara"`. The pair is wrapped in `<div role="group" aria-labelledby="pickone-question">`.
- The result is announced in an `aria-live="polite"` region: *"Carbonara wins. 61% agree."* The region is separate from the visual reveal so screen-reader users are not racing the animation; the auto-advance to the next pair is **delayed until the live region has been given `[CONFIG: A11Y_ANNOUNCE_MS = 1600]`** when a screen reader is likely in use (detected via `prefers-reduced-motion` as a proxy, plus a persisted user preference toggle in the account menu: "Slower pace").
- Contrast ≥ 4.5:1 for all text, ≥ 3:1 for card borders and focus rings. The winner is **never** indicated by colour alone — it also gets a border weight change and a text label.
- Visible focus ring on every interactive element, `:focus-visible`, never `outline: none`.
- Touch targets ≥ 44×44 CSS px.
- Full keyboard operability with no traps. Swipe has a button equivalent for every gesture.
- Public pages use semantic landmarks (`<header> <nav> <main> <footer>`), one `<h1>` per page, and heading levels that never skip.
- Respects `prefers-color-scheme`; both themes ship at launch.

---

## 6. Domain model

```
                       ┌──────────┐
                       │   User   │
                       └────┬─────┘
              creates       │        owns
        ┌───────────────────┼────────────────────┐
        ▼                                        ▼
   ┌─────────┐                              ┌─────────┐
   │  Item   │◄──────── item_a ─────────┐   │ Battle  │
   │         │◄──────── item_b ───────┐ │   └────┬────┘
   └────┬────┘                        │ │        │
        │ 1                           │ │        │ N
        │                        ┌────┴─┴─────┐  │
        │ N                      │ Comparison │◄─┘
   ┌────▼──────────────┐         └─────┬──────┘
   │ ModerationResult  │               │ (future)
   └───────────────────┘               ├── Comment
                                       ├── Statistic
   ┌───────────────────┐               └── CommunityData
   │   RatingEvent     │  (append-only audit of every rating change)
   └───────────────────┘
```

### 6.1 Entities

**User** — **an actor that can pick.** Not "a person with an account" — that is a `User` with `is_guest = false`.
Key fields: `id`, `email`, `password_hash`, `email_verified_at`, `is_guest`, `is_admin`, `is_active`, `created_at`, `last_seen_at`, `deleted_at`, `settings` (JSONB — reduced-pace toggle, theme).

This is the most important naming decision in the model. A guest and a registered user are **the same entity in different states**, so:

- every invariant is expressed in terms of `user_id` and needs no `is_guest` branch;
- registration is an `UPDATE` on an existing row, not a merge ([§4.1](#41-registration-and-guest-conversion));
- guests and members share one partial unique index, one battle transaction, one analytics view.

The alternative — a separate `guest_sessions` table with a nullable `battles.guest_id` — would double every constraint, every query and every test for no benefit. Do not do it.

**Item** — a thing that can be picked. Plain text, **immutable in MVP**.
Key fields: `id`, `text` (display form), `normalized_text` (dedupe key, unique), `slug` (unique, immutable), `created_by_user_id`, `status`, `rating`, **`rating_deviation`**, `battle_count`, `win_count`, `loss_count`, `skip_count`, `created_at`, `published_at`, `rating_updated_at`.

`rating_deviation` is present regardless of which rating system is chosen ([§10.2](#102-the-three-candidate-systems)) — Glicko maintains it, Elo and EGF leave it at its initial value. Carrying the column from day one is what makes the system swappable without a migration on the largest table in the database.
`status ∈ {PENDING_MODERATION, APPROVED, REVIEW, REJECTED, HIDDEN}`. Only `APPROVED` items are eligible for matchmaking, appear in rankings, or have indexable pages.
Denormalised counters (`battle_count`, `win_count`, `loss_count`) are maintained inside the same transaction that records the battle. They are a cache; a reconciliation job verifies them nightly against `battles`.

**Comparison** — the permanent, first-class relationship between two items. **This is the entity the public cares about.**
Key fields: `id`, `item_a_id`, `item_b_id`, `slug`, `battle_count`, `a_win_count`, `b_win_count`, `skip_count`, `first_battle_at`, `last_battle_at`, `created_at`.
`[INVARIANT]` `item_a_id < item_b_id`, enforced by a `CHECK`. `UNIQUE (item_a_id, item_b_id)`. "Carbonara vs Pizza" and "Pizza vs Carbonara" are the same row, always.
A Comparison is created lazily, on first matchmaking, and then lives forever. It accumulates battles, and later comments, statistics and community data. It is never deleted, even if an item is hidden.

**Battle** — one user's short-lived interaction with a Comparison. Ephemeral in intent, permanent as a record.
Key fields: `id`, `comparison_id`, `user_id` (**nullable** — see [§13.7](#137-account-deletion-and-the-audit-trail)), `status`, `winner_id`, `created_at`, `expires_at`, `completed_at`, `item_a_rating_before/after`, `item_b_rating_before/after`, `item_a_rd_before/after`, `item_b_rd_before/after`, `rating_system_version`, `decision_ms`, `source`.
`status ∈ {PENDING, COMPLETED, SKIPPED, EXPIRED}`. See §9.
The rating snapshots live on the battle so that any result is explainable forever without replaying history.

**ModerationResult** — append-only record of one moderation evaluation of one item.
Key fields: `id`, `item_id`, `provider`, `model`, `decision`, `scores` (JSONB), `raw_response` (JSONB), `policy_version`, `latency_ms`, `created_at`.
An item may have several: the automatic pass, a re-check after a provider change, an admin override.

**RatingEvent** — append-only audit of every rating change to every item. One battle produces two rows.
Key fields: `id`, `item_id`, `battle_id`, `rating_before`, `rating_after`, `rd_before`, `rd_after`, `delta`, `expected`, `actual`, `opponent_id`, `opponent_rating_before`, `opponent_rd_before`, `terms` (JSONB — the system-specific intermediates: `con`/`bonus` for EGF, `g`/`d2`/`K` for Glicko/Elo), `rating_system_version`, `created_at`.
This is the auditability requirement, and it is also the **enabling mechanism for Phase 2 and Phase 3**: because every input to every rating change is stored, ratings can be recomputed over any subset of battles — a demographic segment, or the merged history of two items — without replaying the product.

### 6.2 Supporting entities

**Session** — server-side session. `id`, `user_id`, `token_hash`, `csrf_secret`, `expires_at`, `created_at`, `last_seen_at`, `user_agent_hash`, `ip_hash`, `revoked_at`.
**EmailToken** — verification and password reset. `id`, `user_id`, `purpose`, `token_hash`, `expires_at`, `used_at`.
**ItemReport** — user-submitted abuse report. `id`, `item_id`, `reporter_user_id`, `reason`, `created_at`, `resolved_at`, `resolution`.
**RateLimitCounter** — Postgres-backed fixed-window counters. `key`, `window_start`, `count`. (Replaceable by Redis when it earns its place; see §17.)
**OutboxJob** — minimal Postgres job queue for emails and other side effects. `id`, `kind`, `payload`, `run_after`, `attempts`, `locked_at`, `completed_at`, `last_error`.
**AnalyticsEvent** — append-only client/UI event stream. `id`, `user_id`, `session_id`, `name`, `props` (JSONB), `occurred_at`. Core-loop metrics are derived from `battles`, not from this table (§15).

### 6.3 Deliberate modelling decisions

- **A Battle is not the relationship between two items.** It is one user's momentary encounter with a Comparison. This is why comparison pages can exist, accumulate, and be permanent while battles expire in under a minute.
- **Comparisons are only addressable if they exist.** There is no route that materialises a comparison page for a pair that has never been drawn. With 10,000 items there are ~50 million possible pairs; only the ones that actually happened are pages. This single decision prevents the thin-content explosion described in §14.
- **Ratings live on Item, history lives on RatingEvent.** The item row is the fast read path; the event table is the truth and the audit trail.
- **The pairwise mechanism is not hard-wired to items.** `Comparison` and `Battle` reference items directly in MVP (simpler, faster, fewer joins), but the *rating engine*, the *matchmaking module* and the *battle lifecycle service* are written against abstract `subject_id` pairs and know nothing about items. Phase 4's "which translation sounds better" reuses the engine without a rewrite. This costs nothing now — it is a matter of function signatures, not tables.

---

## 7. Database design

PostgreSQL 16. All timestamps `TIMESTAMPTZ`, all ids `UUID` (v7 for time-ordered locality via `uuid_generate_v7()` or an application-side generator), all money-like numbers `NUMERIC`.

### 7.1 Enums

```sql
CREATE TYPE item_status        AS ENUM ('PENDING_MODERATION','APPROVED','REVIEW','REJECTED','HIDDEN');
CREATE TYPE battle_status      AS ENUM ('PENDING','COMPLETED','SKIPPED','EXPIRED');
CREATE TYPE moderation_decision AS ENUM ('APPROVED','REVIEW','REJECTED','ERROR');
CREATE TYPE email_token_purpose AS ENUM ('VERIFY_EMAIL','RESET_PASSWORD');
```

### 7.2 Core tables

```sql
CREATE TABLE users (
    id                UUID PRIMARY KEY,
    email             CITEXT UNIQUE,                    -- NULL only when is_guest
    password_hash     TEXT,                             -- NULL only when is_guest
    email_verified_at TIMESTAMPTZ,
    is_guest          BOOLEAN     NOT NULL DEFAULT FALSE,
    is_admin          BOOLEAN     NOT NULL DEFAULT FALSE,
    is_active         BOOLEAN     NOT NULL DEFAULT TRUE,
    settings          JSONB       NOT NULL DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT users_credentials_ck CHECK (
        (is_guest AND email IS NULL AND password_hash IS NULL)
        OR (NOT is_guest AND email IS NOT NULL AND password_hash IS NOT NULL)
    )
);
-- guest janitor: reap guests that never completed a battle
CREATE INDEX users_guest_reap_idx ON users (last_seen_at) WHERE is_guest;

CREATE TABLE items (
    id                 UUID PRIMARY KEY,
    text               TEXT        NOT NULL,
    normalized_text    TEXT        NOT NULL,
    slug               TEXT        NOT NULL,
    created_by_user_id UUID        REFERENCES users(id) ON DELETE SET NULL,
    status             item_status NOT NULL DEFAULT 'PENDING_MODERATION',
    rating             NUMERIC(10,4) NOT NULL DEFAULT 0.0000,   -- [§10.4] 0 is the origin, not "unrated"
    rating_deviation   NUMERIC(10,4) NOT NULL DEFAULT 350.0000,
    battle_count       INTEGER     NOT NULL DEFAULT 0,
    win_count          INTEGER     NOT NULL DEFAULT 0,
    loss_count         INTEGER     NOT NULL DEFAULT 0,
    skip_count         INTEGER     NOT NULL DEFAULT 0,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at       TIMESTAMPTZ,
    rating_updated_at  TIMESTAMPTZ,
    CONSTRAINT items_text_len_ck   CHECK (char_length(text) BETWEEN 2 AND 64),
    CONSTRAINT items_counts_ck     CHECK (win_count + loss_count <= battle_count),
    CONSTRAINT items_rating_ck     CHECK (rating > -100000 AND rating < 100000),
    CONSTRAINT items_rd_ck         CHECK (rating_deviation > 0 AND rating_deviation <= 350)
);
CREATE UNIQUE INDEX items_normalized_text_uq ON items (normalized_text);
CREATE UNIQUE INDEX items_slug_uq            ON items (slug);
-- ranked items only: RD gates leaderboard entry under Glicko  [§10.5]
CREATE INDEX items_ranking_idx  ON items (rating DESC, id)
    WHERE status = 'APPROVED' AND rating_deviation < 100;
CREATE INDEX items_pool_idx     ON items (rating)          WHERE status = 'APPROVED';
CREATE INDEX items_coldstart_idx ON items (rating_deviation DESC, battle_count)
    WHERE status = 'APPROVED';
CREATE INDEX items_moderation_idx ON items (status, created_at) WHERE status IN ('PENDING_MODERATION','REVIEW');

CREATE TABLE comparisons (
    id             UUID PRIMARY KEY,
    item_a_id      UUID NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
    item_b_id      UUID NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
    slug           TEXT NOT NULL,
    battle_count   INTEGER NOT NULL DEFAULT 0,
    a_win_count    INTEGER NOT NULL DEFAULT 0,
    b_win_count    INTEGER NOT NULL DEFAULT 0,
    skip_count     INTEGER NOT NULL DEFAULT 0,
    first_battle_at TIMESTAMPTZ,
    last_battle_at  TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT comparisons_canonical_ck CHECK (item_a_id < item_b_id),
    CONSTRAINT comparisons_counts_ck    CHECK (a_win_count + b_win_count <= battle_count)
);
CREATE UNIQUE INDEX comparisons_pair_uq ON comparisons (item_a_id, item_b_id);
CREATE UNIQUE INDEX comparisons_slug_uq ON comparisons (slug);
CREATE INDEX comparisons_item_a_idx ON comparisons (item_a_id, battle_count DESC);
CREATE INDEX comparisons_item_b_idx ON comparisons (item_b_id, battle_count DESC);
CREATE INDEX comparisons_indexable_idx ON comparisons (battle_count DESC, last_battle_at DESC);

CREATE TABLE battles (
    id                    UUID PRIMARY KEY,
    comparison_id         UUID NOT NULL REFERENCES comparisons(id) ON DELETE RESTRICT,
    -- NULL means "the actor deleted their account". The battle, its rating effect
    -- and every counter it fed remain valid and permanent.  [§13.7]
    user_id               UUID REFERENCES users(id) ON DELETE SET NULL,
    status                battle_status NOT NULL DEFAULT 'PENDING',
    winner_id             UUID REFERENCES items(id) ON DELETE RESTRICT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at            TIMESTAMPTZ NOT NULL,
    completed_at          TIMESTAMPTZ,
    item_a_rating_before  NUMERIC(10,4),
    item_a_rating_after   NUMERIC(10,4),
    item_a_rd_before      NUMERIC(10,4),
    item_a_rd_after       NUMERIC(10,4),
    item_b_rating_before  NUMERIC(10,4),
    item_b_rating_after   NUMERIC(10,4),
    item_b_rd_before      NUMERIC(10,4),
    item_b_rd_after       NUMERIC(10,4),
    rating_system_version TEXT,
    decision_ms           INTEGER,
    source                TEXT,          -- 'web' | 'seed' | 'backfill'
    CONSTRAINT battles_winner_ck CHECK (
        (status = 'COMPLETED' AND winner_id IS NOT NULL AND completed_at IS NOT NULL)
        OR (status <> 'COMPLETED' AND winner_id IS NULL)
    ),
    CONSTRAINT battles_expiry_ck CHECK (expires_at > created_at)
);

-- [INVARIANT] at most one pending battle per actor, enforced by the database.
-- NULL user_id (deleted actor) is exempt: NULLs are distinct in a unique index,
-- and a deleted actor's battles are always already terminal.
CREATE UNIQUE INDEX one_pending_battle_per_user
    ON battles (user_id) WHERE status = 'PENDING' AND user_id IS NOT NULL;

CREATE INDEX battles_sweeper_idx    ON battles (expires_at) WHERE status = 'PENDING';
CREATE INDEX battles_comparison_idx ON battles (comparison_id, completed_at DESC)
    WHERE status = 'COMPLETED';
CREATE INDEX battles_user_recent_idx ON battles (user_id, created_at DESC);
CREATE INDEX battles_analytics_idx   ON battles (created_at, status);
```

Note on `battles_winner_ck`: `winner_id` membership in the comparison cannot be expressed as a table-level `CHECK` (it would require a subquery). It is enforced in the completion transaction *and* by a trigger-free guarantee: the `UPDATE` statement that completes a battle includes `AND winner_id IN (comparison.item_a_id, comparison.item_b_id)` derived from the row already locked in the same transaction. A nightly reconciliation job asserts zero violations.

### 7.3 Supporting tables

```sql
CREATE TABLE rating_events (
    id                    BIGSERIAL PRIMARY KEY,
    item_id               UUID NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    battle_id             UUID NOT NULL REFERENCES battles(id) ON DELETE CASCADE,
    opponent_id           UUID NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    rating_before         NUMERIC(10,4) NOT NULL,
    rating_after          NUMERIC(10,4) NOT NULL,
    rd_before             NUMERIC(10,4) NOT NULL,
    rd_after              NUMERIC(10,4) NOT NULL,
    delta                 NUMERIC(10,4) NOT NULL,
    opponent_rating_before NUMERIC(10,4) NOT NULL,
    opponent_rd_before    NUMERIC(10,4) NOT NULL,
    expected              NUMERIC(10,8) NOT NULL,
    actual                NUMERIC(2,1)  NOT NULL,
    -- system-specific intermediates: {con,bonus} for EGF, {g,d2} for Glicko, {k} for Elo
    terms                 JSONB NOT NULL DEFAULT '{}',
    rating_system_version TEXT NOT NULL,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX rating_events_battle_item_uq ON rating_events (battle_id, item_id);
CREATE INDEX rating_events_item_idx ON rating_events (item_id, created_at DESC);

CREATE TABLE moderation_results (
    id             UUID PRIMARY KEY,
    item_id        UUID NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    provider       TEXT NOT NULL,
    model          TEXT,
    decision       moderation_decision NOT NULL,
    scores         JSONB NOT NULL DEFAULT '{}',
    raw_response   JSONB,
    policy_version TEXT NOT NULL,
    latency_ms     INTEGER,
    reviewed_by_user_id UUID REFERENCES users(id),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX moderation_results_item_idx ON moderation_results (item_id, created_at DESC);

CREATE TABLE sessions (
    id             UUID PRIMARY KEY,
    user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash     BYTEA NOT NULL,
    csrf_secret    BYTEA NOT NULL,
    expires_at     TIMESTAMPTZ NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at     TIMESTAMPTZ,
    user_agent_hash BYTEA,
    ip_hash        BYTEA
);
CREATE UNIQUE INDEX sessions_token_uq ON sessions (token_hash);
CREATE INDEX sessions_user_idx ON sessions (user_id) WHERE revoked_at IS NULL;

CREATE TABLE email_tokens (
    id         UUID PRIMARY KEY,
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose    email_token_purpose NOT NULL,
    token_hash BYTEA NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX email_tokens_hash_uq ON email_tokens (token_hash);

CREATE TABLE item_reports (
    id               UUID PRIMARY KEY,
    item_id          UUID NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    -- SET NULL, not CASCADE: a deleted account must not un-hide a reported item
    reporter_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    reason           TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    resolved_at      TIMESTAMPTZ,
    resolution       TEXT
);
CREATE UNIQUE INDEX item_reports_once_uq ON item_reports (item_id, reporter_user_id)
    WHERE reporter_user_id IS NOT NULL;

CREATE TABLE outbox_jobs (
    id           UUID PRIMARY KEY,
    kind         TEXT NOT NULL,
    payload      JSONB NOT NULL,
    run_after    TIMESTAMPTZ NOT NULL DEFAULT now(),
    attempts     INTEGER NOT NULL DEFAULT 0,
    locked_at    TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    last_error   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX outbox_ready_idx ON outbox_jobs (run_after)
    WHERE completed_at IS NULL AND locked_at IS NULL;

CREATE TABLE rate_limits (
    key          TEXT NOT NULL,
    window_start TIMESTAMPTZ NOT NULL,
    count        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (key, window_start)
);

CREATE TABLE analytics_events (
    id          BIGSERIAL PRIMARY KEY,
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    session_id  UUID,
    name        TEXT NOT NULL,
    props       JSONB NOT NULL DEFAULT '{}',
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX analytics_events_name_time_idx ON analytics_events (name, occurred_at DESC);
```

### 7.4 Read-optimised views

```sql
-- Refreshed every [CONFIG: RANKINGS_REFRESH_SECONDS = 300] by the worker.
CREATE MATERIALIZED VIEW item_rankings AS
SELECT
    row_number() OVER (ORDER BY rating DESC, battle_count DESC, id) AS rank,
    id, slug, text, rating, rating_deviation, battle_count, win_count, loss_count
FROM items
WHERE status = 'APPROVED'
  -- Glicko: RD gates entry, and the threshold is derived, not guessed  [§10.5]
  AND rating_deviation < 100          -- [CONFIG: RANKED_RD]
  -- Elo / EGF fallback: AND battle_count >= 5   [CONFIG: RANKINGS_MIN_BATTLES]
ORDER BY rating DESC, battle_count DESC, id;

CREATE UNIQUE INDEX item_rankings_rank_uq ON item_rankings (rank);
CREATE UNIQUE INDEX item_rankings_id_uq   ON item_rankings (id);
-- REFRESH MATERIALIZED VIEW CONCURRENTLY item_rankings;
```

The materialised view makes `/rankings?page=N` an indexed range scan rather than a sort of the whole table, and gives every item page a cheap `rank` lookup. It is a *cache*: staleness of up to 5 minutes is acceptable and invisible.

### 7.5 Migrations

Alembic, one migration per milestone, forward-only in production. Rules:

- Every migration must be safe to run against a live database: no long `ACCESS EXCLUSIVE` locks, `CREATE INDEX CONCURRENTLY` for indexes on populated tables (outside a transaction), new columns nullable-or-defaulted, no `ALTER TYPE` on a live enum without the `ADD VALUE` form.
- Data backfills go in separate migrations from schema changes.
- The test suite runs migrations from empty on every CI run, and asserts that the resulting schema matches the ORM metadata (`alembic check`-style autogenerate diff must be empty).

---

## 8. API design

Base: `/api`. JSON only. Same-origin with the frontend (`pickone.app` serves both; `/api/*` is reverse-proxied to FastAPI) so session cookies can stay `SameSite=Lax`.

### 8.1 Conventions

- **Auth:** opaque session token in an `httpOnly; Secure; SameSite=Lax; Path=/` cookie named `po_session`. No `Authorization` header, no JWT in MVP. **A session belongs to an *actor*, which may be a guest** — endpoints that require a registered or verified account say so explicitly and return `401` otherwise.
- **CSRF:** every unsafe method (`POST/PUT/PATCH/DELETE`) requires an `X-PickOne-CSRF` header matching a double-submit token derived from the session's `csrf_secret`. Returned by `/api/auth/login` and `/api/me`.
- **Errors:** one envelope, always.
  ```json
  { "error": { "code": "battle_expired", "message": "That one timed out.", "details": {} } }
  ```
  `message` is user-safe copy in the product lexicon; the client may display it verbatim.
- **Rate limits:** `429` with `Retry-After`. Headers `X-RateLimit-Limit`, `X-RateLimit-Remaining` on limited endpoints.
- **Idempotency:** achieved by design (the battle id *is* the idempotency key), not by an `Idempotency-Key` header.
- **Timestamps:** RFC 3339 UTC with `Z`.
- **Ratings are integers on the wire** (rounded for display); full precision stays server-side. `rating_deviation` is never exposed publicly — only the derived `ranked: true|false` and, on an unranked item's own page, its battle count.

### 8.2 Authentication

```http
POST /api/auth/register
{ "email": "a@b.com", "password": "..." }
→ 201 { "user": { "id": "...", "email": "a@b.com", "email_verified": false,
                  "converted_from_guest": true, "picks_kept": 37 },
        "csrf_token": "..." }                       + Set-Cookie: po_session=...
→ 409 { "error": { "code": "email_taken" } }        ← including while holding a guest session:
                                                       ask them to log in, never auto-merge
→ 422 { "error": { "code": "weak_password", "details": { "min_length": 10 } } }
```
If the request carries a guest session, the guest's `users` row is converted **in place** — same `user_id`, same battles, same history ([§4.1](#41-registration-and-guest-conversion)). `picks_kept` drives the confirmation copy: *"Added. 37 picks kept."*
```http
POST /api/auth/login
{ "email": "a@b.com", "password": "..." }
→ 200 { "user": {...}, "csrf_token": "..." }        + Set-Cookie
→ 401 { "error": { "code": "invalid_credentials" } }   ← identical for unknown email and bad password
→ 429 { "error": { "code": "too_many_attempts" } }
```
```http
POST /api/auth/logout                    → 204   (session revoked, cookie cleared)
POST /api/auth/verify   { "token": "..." } → 200 { "user": {...} }  | 410 token_expired | 400 token_invalid
POST /api/auth/verify/resend             → 202   (always 202; rate limited 3/hour/user)
POST /api/auth/password-reset/request { "email": "..." } → 202   (always 202, no enumeration)
POST /api/auth/password-reset/confirm { "token": "...", "password": "..." }
     → 200   (all sessions for the user revoked, a fresh one issued)
GET  /api/me → 200 { "user": {...}, "csrf_token": "...", "limits": { "items_remaining_today": 17 } }
             | 401
```

### 8.3 Items

```http
POST /api/items       (registered + verified email required — guests get 401)
{ "text": "Fitting bed sheets" }

→ 201 { "item": { "id": "...", "text": "Fitting bed sheets", "slug": "fitting-bed-sheets",
                  "status": "APPROVED", "rating": 100 },
        "message": "Added." }
→ 202 { "item": { ..., "status": "REVIEW" },
        "message": "Added. We'll take a quick look before it joins." }
→ 409 { "error": { "code": "already_exists",
                   "details": { "slug": "fitting-bed-sheets" } } }
→ 422 { "error": { "code": "rejected", "message": "We can't add that one." } }
→ 422 { "error": { "code": "invalid_text", "details": { "reason": "too_long", "max": 64 } } }
→ 401 { "error": { "code": "account_required",
                   "message": "Make an account to add one." } }        ← guest
→ 429 { "error": { "code": "rate_limited" } }
```

```http
GET /api/items/{slug}                (public, cacheable)
→ 200 {
    "item": { "id": "...", "text": "Carbonara", "slug": "carbonara",
              "rating": 487, "rank": 1, "ranked": true, "battle_count": 1592,
              "win_count": 1204, "loss_count": 388, "win_rate": 0.756,
              "created_at": "..." },
    -- an unranked item instead carries: "rank": null, "ranked": false  [§10.5]
    "rivals":       [ { "comparison_slug": "carbonara-vs-pizza", "item": {...},
                        "battle_count": 8421, "win_rate": 0.61 } ],   -- closest by rating
    "biggest_wins": [ { "comparison_slug": "...", "item": {...}, "win_rate": 0.97 } ],
    "recent":       [ { "opponent": {...}, "won": true, "at": "..." } ]
  }
→ 404 | 410 (item HIDDEN or REJECTED after publication)
```

```http
GET /api/rankings?page=1&per_page=50    (public, cacheable, per_page ∈ {25,50,100})
→ 200 { "page": 1, "per_page": 50, "total": 12043, "total_pages": 241,
        "items": [ { "rank": 1, "slug": "carbonara", "text": "Carbonara",
                     "rating": 2481, "battle_count": 1592,
                     "win_count": 1204, "loss_count": 388 } ] }
```

```http
GET /api/comparisons/{slug}             (public, cacheable)   slug = "carbonara-vs-pizza"
→ 200 {
    "comparison": { "slug": "carbonara-vs-pizza", "battle_count": 8421,
                    "first_battle_at": "...", "last_battle_at": "..." },
    "a": { "item": {...}, "wins": 5137, "share": 0.610 },
    "b": { "item": {...}, "wins": 3284, "share": 0.390 },
    "trend": [ { "week": "2026-08-17", "a_share": 0.62, "battles": 310 } ],
    "indexable": true
  }
→ 301 Location: /api/comparisons/carbonara-vs-pizza     ← if the slug order is reversed
→ 404                                                    ← if the pair has never battled
```

### 8.4 The battle loop

```http
GET /api/battles/current    (no auth required — creates a guest actor if there is no session)
      ?seed={item_id}       (optional, one-shot, from the "Add one" flow)

→ 200 {
    "battle_id": "018f...",
    "expires_at": "2026-08-26T12:00:60Z",
    "server_time": "2026-08-26T12:00:00Z",
    "items": [
      { "id": "018a...", "text": "Carbonara",          "slug": "carbonara" },
      { "id": "018b...", "text": "Fitting bed sheets", "slug": "fitting-bed-sheets" }
    ]
  }
→ 503 { "error": { "code": "no_items_available" } }     ← catalogue exhausted for this actor
```
A cookie-less request creates the guest actor and returns `Set-Cookie: po_session=…` alongside the battle. This is a **read of the actor's standing pair** that lazily establishes both the actor and the pair ([§9.3](#93-the-standing-pair-invariant)).
`[INVARIANT]` This response contains **no rating, rank, win count or battle count**. `[P4]`
`server_time` lets the client compute the remaining TTL without trusting the device clock.
Repeated calls within the TTL return **the identical `battle_id`** — this endpoint is a `GET` and is safe to retry, refresh and open in five tabs.

```http
POST /api/battles/{battle_id}/pick     (auth + CSRF)
{ "winner_id": "018a...", "decision_ms": 2410 }

→ 200 {
    "result": {
      "battle_id": "018f...",
      "winner_id": "018a...",
      "comparison_slug": "carbonara-vs-fitting-bed-sheets",
      "items": [
        { "id": "018a...", "rating_before": 476, "rating_after": 487, "delta":  11 },
        { "id": "018b...", "rating_before": -19, "rating_after": -30, "delta": -11 }
      ],
      -- ratings are signed integers; 0 is legal and meaningful  [§10.4]
      "crowd": { "winner_share": 0.61, "battle_count": 8421 }   -- omitted below 20 battles
    },
    "next": { "battle_id": "...", "expires_at": "...", "items": [...] }
  }
→ 200 (identical body, replayed)  ← duplicate submission of the SAME winner_id
→ 409 { "error": { "code": "already_decided" } }   ← duplicate with a DIFFERENT winner_id
→ 409 { "error": { "code": "battle_not_pending" } } ← already skipped
→ 410 { "error": { "code": "battle_expired", "message": "That one timed out." } }
→ 404 { "error": { "code": "battle_not_found" } }  ← wrong owner returns 404, not 403
→ 422 { "error": { "code": "winner_not_in_battle" } }
```

```http
POST /api/battles/{battle_id}/skip     (auth + CSRF)
→ 200 { "battle": { "battle_id": "...", "status": "SKIPPED" },
        "next":   { "battle_id": "...", "expires_at": "...", "items": [...] } }
→ 200 (replayed)  ← duplicate skip of an already-SKIPPED battle
→ 409 already_decided     ← already completed
→ 410 battle_expired
```

Design notes on the loop endpoints:

- **`next` is created in a separate transaction**, after the pick transaction commits. If creating `next` fails for any reason, the pick is still durably recorded and the response simply omits `next`; the client falls back to `GET /api/battles/current`. A rating change must never be rolled back because matchmaking hiccuped.
- **Wrong-owner returns `404`, not `403`**, so battle ids are not an oracle for other users' activity.
- **`decision_ms` is client-supplied and untrusted.** It is stored for analytics and bot detection and never used in any rule.

### 8.5 Reporting and admin

```http
POST /api/items/{slug}/report   { "reason": "..." }   (registered)  → 202 | 401 | 409 already_reported
GET  /api/admin/moderation/queue?status=REVIEW               (admin) → 200 { items: [...] }
POST /api/admin/items/{id}/decision { "decision": "APPROVED" | "REJECTED" }  (admin) → 200
```

Admin is a minimal, protected, server-rendered surface. Not a product. See §12.6.

### 8.6 Public non-JSON routes (frontend)

`/`, `/rankings`, `/rankings/page/{n}`, `/item/{slug}`, `/compare/{slug}`, `/play`, `/add`, `/login`, `/register`, `/robots.txt`, `/sitemap.xml`, `/sitemaps/{name}.xml.gz`, `/og/item/{slug}.png`, `/og/compare/{slug}.png`.

---

## 9. Battle state machine

```
                       GET /battles/current
                     (no live pending battle)
                              │
                              ▼
                        ┌───────────┐
        ┌───────────────│  PENDING  │───────────────┐
        │               └─────┬─────┘               │
        │                     │                     │
  POST …/pick           POST …/skip          expires_at < now()
  (valid, unexpired)   (valid, unexpired)   (lazy check or sweeper)
        │                     │                     │
        ▼                     ▼                     ▼
  ┌────────────┐        ┌───────────┐         ┌───────────┐
  │ COMPLETED  │        │  SKIPPED  │         │  EXPIRED  │
  └────────────┘        └───────────┘         └───────────┘
   ratings move          no rating change      no rating change
   counters move         skip counters move    nothing moves
   ← TERMINAL            ← TERMINAL            ← TERMINAL
```

### 9.1 Rules

`[INVARIANT]` **PENDING is the only non-terminal state.** No transition out of `COMPLETED`, `SKIPPED` or `EXPIRED` exists, in code or by admin action.
`[INVARIANT]` **Every actor has exactly one live PENDING battle**, unless their eligible catalogue is exhausted. Enforced by `one_pending_battle_per_user` plus lazy repair on read ([§9.3](#93-the-standing-pair-invariant)).
`[INVARIANT]` **Exactly one `rating_events` pair per `COMPLETED` battle**, enforced by `rating_events_battle_item_uq`.
`[INVARIANT]` A rating change happens **only** on the `PENDING → COMPLETED` transition.

### 9.2 Expiry: lazy plus sweeper

Two mechanisms, both required:

1. **Lazy (authoritative for correctness).** Every read and every mutation of a battle checks `expires_at > now()` inside the transaction. An expired battle is transitioned to `EXPIRED` right there. This is what makes the rule true even if the worker is down.
2. **Sweeper (authoritative for analytics).** The worker runs every `[CONFIG: SWEEPER_INTERVAL_SECONDS = 30]`:
   ```sql
   UPDATE battles SET status = 'EXPIRED'
   WHERE status = 'PENDING' AND expires_at < now();
   ```
   Without it, a user who abandons the site leaves a `PENDING` row forever and expiry-rate metrics lie.

### 9.3 The standing-pair invariant

> **Resolving Q7.** The original framing was "`GET /api/battles/current` creates a battle", which is a `GET` with a side effect and smells. Your reframe is better and I have adopted it:

`[INVARIANT]` **Every actor always has exactly one standing pair waiting for them, unless their eligible catalogue is exhausted.**

Under this framing `GET /api/battles/current` is what it appears to be — **a read of a resource that is guaranteed to exist** — and creation is an implementation detail of maintaining the invariant, performed lazily on read in the same way a cache populates itself or a lazily-initialised singleton constructs itself. The smell disappears, and it disappears for a real reason rather than by relabelling: the operation is idempotent, it returns the same resource on every call within the TTL, and a forged cross-site `GET` achieves nothing an attacker wants (the victim's next pair differs; that is the entire blast radius).

**This is not overengineering, because it is the same code.** No background job pre-creates pairs for idle users — that genuinely *would* be overengineering, and it would create a pending battle for every one of your guest rows. The invariant is maintained lazily, at the moment somebody looks. The value is that "the pair is always there" is now the *stated rule*, so the endpoint's shape follows from the model instead of needing a footnote defending it.

The one place the invariant genuinely cannot hold is catalogue exhaustion — a heavy player who has already seen every eligible pair. That returns `503 no_items_available`, which is the honest answer and a signal to add items ([§11.4](#114-cold-start-and-the-catalogue-floor)).

**Maintaining it, safely under concurrency:**

```
BEGIN
  -- 0. No session cookie? Create the guest actor first.  [§4.0]
  --    Lazy: guests are born here and nowhere else.

  -- 1. Serialise per actor. Cheap, no row needed, released at COMMIT.
  SELECT pg_advisory_xact_lock(hashtextextended('battle:' || :user_id, 0));

  -- 2. Does the standing pair already exist and is it still live?
  SELECT * FROM battles WHERE user_id = :uid AND status = 'PENDING' FOR UPDATE;
     ├─ found and expires_at >  now()  → return it, COMMIT.   (the ordinary read)
     └─ found and expires_at <= now()  → UPDATE … SET status='EXPIRED'; fall through
                                          to re-establish the invariant.

  -- 3. Choose a pair (see §11). Runs inside the transaction but touches
  --    only APPROVED items; takes no locks on them.
  (item_x, item_y) := matchmaker.select_pair(user_id, seed_item_id)
     └─ nothing eligible → ROLLBACK, return 503 no_items_available.

  -- 4. Canonicalise and get-or-create the Comparison.
  (a, b) := (min(item_x, item_y), max(item_x, item_y))    -- by UUID ordering
  INSERT INTO comparisons (…) VALUES (…)
    ON CONFLICT (item_a_id, item_b_id) DO UPDATE SET item_a_id = EXCLUDED.item_a_id
    RETURNING *;                        -- DO UPDATE (not DO NOTHING) so RETURNING always fires

  -- 5. Create the battle.
  INSERT INTO battles (id, comparison_id, user_id, status, created_at, expires_at)
  VALUES (…, 'PENDING', now(), now() + :ttl);
     └─ unique_violation on one_pending_battle_per_user
        → a concurrent request won the race.
          ROLLBACK, then re-read the user's pending battle and return THAT.
          This is a success path, not an error path.
COMMIT
```

The unique-violation branch is the point of the whole design: **the database resolves the race, and the loser of the race gets the winner's battle.** Two tabs, a double-click and a retried request all converge on one battle id.

**Guest actors change nothing here.** A guest is a `users` row, so step 0 is the only addition and every subsequent line is identical. The advisory lock, the partial unique index, the `ON CONFLICT` and the unique-violation recovery are all keyed on `user_id` and are indifferent to how that row came into being.

### 9.4 Battle completion — the atomic transaction

```
BEGIN
  -- 1. Lock the battle row.
  SELECT b.*, c.item_a_id, c.item_b_id
  FROM battles b JOIN comparisons c ON c.id = b.comparison_id
  WHERE b.id = :battle_id
  FOR UPDATE OF b;

  -- 2. Validate. Order matters for correct error codes.
  b IS NULL or b.user_id <> :user_id      → 404 battle_not_found
  b.status = 'COMPLETED'                  → replay: if b.winner_id = :winner_id return the
                                            stored result (200), else 409 already_decided
  b.status IN ('SKIPPED','EXPIRED')       → 409 / 410
  b.expires_at <= now()                   → UPDATE … 'EXPIRED'; COMMIT; 410 battle_expired
  :winner_id NOT IN (c.item_a_id, c.item_b_id) → 422 winner_not_in_battle

  -- 3. Lock both items IN ASCENDING ID ORDER. [INVARIANT: deadlock avoidance]
  SELECT id, rating, rating_deviation FROM items
  WHERE id IN (:a, :b) ORDER BY id FOR UPDATE;

  -- 4. Pure computation, no I/O.
  (new_a, new_b, audit_a, audit_b) := RATING_SYSTEM.apply(
        Rating(rating_a, rd_a), Rating(rating_b, rd_b), winner = :winner_id)
  -- pure: no I/O, no DB, no framework. [§10.2]

  -- 5. Write everything.
  UPDATE items SET rating = new_a.value, rating_deviation = new_a.deviation,
                   battle_count = battle_count + 1,
                   win_count = win_count + (a won), loss_count = loss_count + (a lost),
                   rating_updated_at = now() WHERE id = :a;
  UPDATE items … WHERE id = :b;

  INSERT INTO rating_events (…) VALUES (audit_a), (audit_b);   -- unique on (battle_id, item_id)

  UPDATE comparisons SET battle_count = battle_count + 1,
                         a_win_count  = a_win_count + (a won),
                         b_win_count  = b_win_count + (b won),
                         first_battle_at = COALESCE(first_battle_at, now()),
                         last_battle_at  = now()
  WHERE id = :comparison_id;

  UPDATE battles SET status = 'COMPLETED', winner_id = :winner_id, completed_at = now(),
                     item_a_rating_before = …, item_a_rating_after = …,
                     item_b_rating_before = …, item_b_rating_after = …,
                     rating_system_version = …, decision_ms = :decision_ms
  WHERE id = :battle_id AND status = 'PENDING';
  IF rowcount <> 1 THEN ROLLBACK; retry-from-step-1-once; END IF;   -- belt and braces
COMMIT
```

Notes:

- **Isolation level `READ COMMITTED` is sufficient**, because every mutated row is explicitly locked with `FOR UPDATE` before it is read for computation. Do not use `SERIALIZABLE`; it would add retry noise for no benefit here.
- **Ascending-id lock ordering is not optional.** Two concurrent battles on the same pair, locked in opposite orders, deadlock under load. This is the single most likely production incident in this system.
- The `AND status = 'PENDING'` on the final `UPDATE` plus the `rowcount` assertion is redundant with the `FOR UPDATE` — keep it anyway. It converts a subtle logic error into a loud failure.
- **Skip** uses the same transaction shape, minus steps 3–5, plus `comparisons.skip_count` and `items.skip_count` increments.

### 9.5 Client-side rules

- The client **never** stores or reconstructs battle state beyond the current `battle_id` and `expires_at`.
- The pick button is disabled from `pointerdown` until the response resolves. Optimistic *visuals*, never optimistic *state*.
- On `410`/`409`, the client silently recovers by fetching a new battle. It never retries the same battle.
- Multiple tabs: each tab polls `GET /api/battles/current` on `visibilitychange`, and will receive whatever the shared pending battle currently is. A tab whose `battle_id` no longer matches simply re-renders. No cross-tab coordination, no `BroadcastChannel`, no locks.

---

## 10. Rating system

> **Revised after Q2.** The original brief said "use the EGF Official Rating System as the mathematical foundation" and "do not arbitrarily invent a new rating system". Both still hold — but Elo and Glicko are not inventions, they are the two best-established systems in the field, and the analysis below concluded that **EGF is the weakest of the three fits for PickOne**. The decision is now made by simulation across three *systems* rather than three parameter sets of one.

### 10.1 Why EGF is the wrong shape for this product

Working through the EGF formula produced two findings that reframe the whole question.

**Finding 1 — EGF is Bradley–Terry under a coordinate change.** Substituting `beta(r) = −B·ln(C − r)` into the win probability collapses it to:

```
win_prob(r1, r2) = 1 / (1 + ((C - r1) / (C - r2)) ** B)        with C = 3300, B = 7
```

Only the *ratio of distances from C* matters. The rating scale is a reparameterisation of Bradley–Terry with strength `s = (C − r)^(−B)`. `C` is not a quality ceiling; it is the singularity of the coordinate change. (This closed form is also the numerically stable implementation — no `exp`, no overflow. Whichever system is chosen, this identity stays in the spec because it is how the EGF candidate must be coded.)

**Finding 2 — every distinctive feature of EGF solves a Go problem PickOne does not have.**

| EGF feature | Why it exists in Go | Does PickOne have that problem? |
|---|---|---|
| The `C = 3300` reparameterisation | Calibrates the scale to *stones* — a rating gap must map onto handicap stones, which compress at dan level | **No.** There is no handicap, no stones, and no natural top of the scale. |
| Rating-dependent `con(r)` | A proxy for "stronger players have more established ratings" | **No.** In PickOne, rating level and certainty are unrelated — a brand-new item and a 2,000-battle item can sit at the same rating. |
| The `bonus(r)` term | Counteracts deflation from a continuous influx of *improving* juniors who drain points | **Partly.** New items do enter continuously, but they do not improve, and they never retire. Applied here, `bonus` is a pump with no sink. |
| Draws, colour, handicap | Core to Go | **Removed**, as instructed. |

And the two concrete risks this creates, quantified under EGF's own defaults at its original `INITIAL_RATING = 100` (EGF is not translation-invariant, so its numbers are quoted at the origin it was designed for — [§10.4](#104-zero-is-the-origin-and-the-sign-is-the-product)):

- **Entry volatility.** `con(100) = 84.45`. A new item's first pick is worth ±42 points. The first few battles dominate its rating for a long time.
- **Inflation with no sink.** `bonus(100) = 5.5` is injected on *every* battle regardless of outcome. Items never retire, so the population drifts upward until it reaches `r ≳ 2400`, where `bonus` decays and `con` has collapsed to ~10 — differentiation stops and the leaderboard freezes near the ceiling.

Both risks are fixable by parameter search. But fixing them means tuning away the parts of EGF that make it EGF, at which point a system designed for an open-ended population is the better starting point.

**The deeper mismatch:** PickOne's real problem is not "how strong is this item" — it is **"how sure are we?"** Battle counts are heavily skewed; some items have 3 battles and some have 3,000. EGF has no representation of certainty at all. Glicko's entire contribution is exactly that representation.

### 10.2 The three candidate systems

All three implement one protocol, so the choice is a config value and a simulation result, not a rewrite.

```python
class RatingSystem(Protocol):
    version: str                       # written to every battle and rating_event
    def initial(self) -> Rating: ...   # Rating = (value, deviation)
    def win_prob(self, a: Rating, b: Rating) -> float: ...
    def apply(self, a: Rating, b: Rating, winner: Side) -> Outcome: ...
        # Outcome carries both new Ratings AND the full audit payload for rating_events
```

`Rating` is `(value, deviation)` for every system. Elo and EGF simply report a constant deviation and ignore it. This one decision — a two-field rating from the start — is what lets the systems be swapped without a migration.

---

#### **Candidate A — Glicko-1, incremental. ★ Recommended.**

```
q  = ln(10) / 400 ≈ 0.0057565

g(RD)            = 1 / sqrt(1 + 3·q²·RD² / π²)
E(r, rj, RDj)    = 1 / (1 + 10^( −g(RDj)·(r − rj) / 400 ))
d²               = 1 / ( q² · g(RDj)² · E · (1 − E) )

r'  = r + ( q / (1/RD² + 1/d²) ) · g(RDj) · (s − E)
RD' = max( sqrt( 1 / (1/RD² + 1/d²) ), RD_MIN )
```

Both items update from the **pre-battle snapshot** of the other, exactly as EGF does. `s ∈ {0, 1}`; there are no draws.

| Parameter | Default | Meaning |
|---|---:|---|
| `INITIAL_RATING` | **0.0** | the origin — see [§10.4](#104-zero-is-the-origin-and-the-sign-is-the-product) |
| `INITIAL_RD` | 350.0 | Glicko's standard "we know nothing" |
| `RD_MIN` | 30.0 | floor on certainty |
| `RD_MAX` | 350.0 | cap |
| `C_INFLATE` | **0.0** | RD growth for inactive items — see below |
| `RANKED_RD` | 100.0 | RD below which an item joins the leaderboard |

**Why this fits PickOne better than anything else:**

1. **RD *is* the certainty model.** A new item at RD 350 moves fast; after ~10–20 battles RD drops near 100 and it stabilises. This replaces a hand-tuned provisional K-factor with something the model derives.
2. **It solves the skewed-battle-count problem natively.** An item with 3 battles is *marked* as uncertain, in the data, rather than being indistinguishable from an item with 3,000.
3. **`g(RDj)` damps updates against uncertain opponents.** A 2,000-battle item that beats a brand-new item barely moves — which is correct, and which EGF and Elo both get wrong.
4. **It deletes machinery.** No ceiling, no singularity, no clamp, no `bonus`, no inflation pump, no provisional K, and no `RANKINGS_MIN_BATTLES` hack (RD replaces it — see §10.5). **Glicko-1 is a net reduction in complexity versus the EGF adaptation**, which is the opposite of what "add Glicko" usually means.
5. **No inflation.** Approximately conserving, with no systematic pump. `GATE-R3` becomes near-trivial to pass.

**The honest caveats:**

- **Glicko assumes rating periods of ~10–15 games; we apply it per battle.** This is the standard incremental approximation used by most online implementations, and its artifact is that RD shrinks slightly faster than the model intends — items become "certain" a little too early. `RD_MIN` bounds the damage and the simulator measures it (`GATE-R7`, calibration).
  The alternative — true batch periods computed hourly in the worker — is **rejected on product grounds**: the pick response shows a rating delta immediately ([§4.3](#43-the-repeated-loop)), and batching would make that impossible. Incremental is a UX-driven decision, not an oversight.
- **`C_INFLATE = 0` for MVP.** RD normally grows during inactivity to model a competitor going rusty. An item's quality does not drift — but the *population's taste* does, slowly and seasonally ("sunshine" in January versus July). Zero is the right MVP default; a small non-zero `c` is the natural first post-launch experiment, and it is one config value.

#### **Candidate B — Elo with a battle-count K-schedule**

```
E   = 1 / (1 + 10^((rb − ra) / 400))
K(n) = K_HIGH if n < N1 else K_MID if n < N2 else K_LOW      # 64 / 32 / 16, N1=15, N2=50
r'  = r + K(n) · (s − E)
```

Exactly zero-sum, four lines, universally understood, impossible to get subtly wrong. The K-schedule is a crude hand-rolled substitute for RD: it approximates certainty by battle count, which is a decent proxy but carries no information about *opponent* uncertainty, and it needs `RANKINGS_MIN_BATTLES` back to stop a one-lucky-win item topping the leaderboard.

**Take it if** the simulation shows Glicko's incremental artifacts to be material, or if maximum simplicity is worth losing the certainty model. It is a genuinely respectable answer, not a straw man.

#### **Candidate C — EGF-adapted (the original brief)**

Retained as the baseline so the comparison is honest and the original instruction is actually tested rather than argued away. Parameterised as before: `C`, `B`, `S`, `A`, `K_SCALE`, `R_BONUS`, `D`, `E`, `R_FLOOR`, `CEIL_MARGIN`, `BONUS_ENABLED`, with the three sub-profiles (`egf-faithful`, `entry-anchored-bonus` with `R_BONUS = 300, D = 100`, and `calm` with `S = 370`). Golden values for `egf-faithful`:

| `r` | `con(r)` | `bonus(r)` | | matchup | `win_prob` |
|---:|---:|---:|---|---|---:|
| 0 | 88.7104 | 5.750000 | | 100 vs 100 | 0.5000 |
| 100 | 84.4485 | 5.500000 | | 200 vs 100 | 0.5553 |
| 500 | 68.2032 | 4.500000 | | 500 vs 100 | 0.7180 |
| 1000 | 49.7871 | 3.250000 | | 1000 vs 100 | 0.9098 |
| 2000 | 19.9830 | 0.754649 | | 2600 vs 2500 | 0.7180 |
| 2300 | 13.1326 | 0.138629 | | 3200 vs 3100 | 0.9922 |
| 3000 | 1.9131 | 0.000032 | | | |

Note that `2600 vs 2500` and `500 vs 100` are **identical** — only the ratio of distances from `C` matters, so a rating point near the ceiling is worth vastly more than one near the floor. A leader at 2,600 becomes very hard to displace. That is the frozen-leaderboard risk, visible in a table.

### 10.3 What Glicko-2 would add, and why it is the overengineered choice

Glicko-2 adds a per-competitor **volatility** `σ`, updated by an iterative root-find (Illinois algorithm) each period. `σ` models a competitor whose *true strength changes over time* — form, training, decline.

**An item's quality does not change.** "Carbonara" is exactly as good next month. What changes is the population's taste, slowly and collectively, which is a property of the electorate rather than of any one item. Glicko-2's headline feature therefore models something that does not happen here, while adding an iterative solver with convergence edge cases to the hottest transaction in the system.

**Recommendation: no.** Not for complexity's sake — because the thing it buys is not present. If, post-launch, ratings prove to drift in ways RD cannot track (a real, measurable finding), revisit it then with evidence. Until then it is machinery in search of a problem. `[P7]`

### 10.4 Zero is the origin, and the sign is the product

**Every item starts at `INITIAL_RATING = 0`.**

Glicko and Elo are approximately conserving on a linear 400-point scale, so the population mean stays wherever the starting value puts it. Set that value to zero and the mean sits at zero — which turns the arithmetic sign into a fact about the world:

```
Carbonara            +487
Rain                  +31
Monday                −18
Doing taxes          −312
Fitting bed sheets   −406
```

**Positive means people pick it more often than not. Negative means they don't.** Zero is dead even. Nobody has to learn a scale, know a maximum, or compare against an arbitrary starting number — the sign carries the meaning on its own, and the magnitude is just "by how much".

This is strictly better than the original `INITIAL_RATING = 100`, for four reasons:

1. **It redeems the negatives instead of tolerating them.** Under a conserving system, roughly half the catalogue ends up below the starting value no matter what that value is. At 100, a negative rating meant "worse than average by more than 100 points" — an arbitrary threshold that means nothing. At 0, negative means *below average*, which is a real fact. The negatives stop being an artifact to explain away and become the most legible thing on the page.
2. **100 invites a misreading that 0 does not.** `100` reads as a full score, a percentage, or a maximum — so an item at `2,481` looks like a bug, and an item at `100` looks perfect rather than untested. Zero has no such collision.
3. **It is free for both recommended systems.** Elo and Glicko are **translation-invariant**: the origin is an arbitrary label, and moving it changes no dynamics whatsoever. `INITIAL_RATING = 0` is a one-line config change with zero consequences for convergence, calibration or matchmaking.
4. **It is one more strike against the EGF candidate.** EGF is *not* translation-invariant — `con(r)` and `beta(r)` reference absolute distance from `C`, so moving the origin genuinely changes the dynamics, and `R_FLOOR = 0` would now clamp every item at its starting value. Choosing Candidate C means re-anchoring `C`, `R_BONUS` and `R_FLOOR` as well. The two systems worth choosing accept this change for free; the one that resists it is the one already ranked last.

**What the sign does and does not promise.** Precisely, a positive rating means *above the population average*. The looser reading — "wins more battles than it loses" — is a very good approximation but not a guarantee: matchmaking pulls records toward 50%, since the `NEIGHBOURHOOD` strategy (50% of battles) deliberately pairs items with similar-rated opponents. The two signs disagree least reliably in the middle of the table, where both are near zero and a handful of battles flips either one.

That is a checkable claim, not a hope, so it is checked: **`GATE-R9` (sign agreement)** measures the share of ranked items whose rating sign matches the sign of `win_count − loss_count`. Above 85%, the product may use the plain language — *"people pick it more often than not"* — in copy. Below that, the copy must say **"above average"** / **"below average"** instead, which is always exactly true. **The wording of the product is decided by the simulation, not by preference.**

**Display rules:**

- Ratings are always rendered **with an explicit sign**: `+487`, `−312`, `0`. Without the leading `+`, a bare `487` does not signal that the sign is meaningful.
- Use a real minus sign (U+2212), not a hyphen.
- The large persistent number is the rating; the small transient number after a pick is the delta. Never show both at the same size in the same place — two signed numbers side by side is the one place this scheme can confuse.
- Sign is **never** conveyed by colour alone ([§5.7](#57-accessibility-wcag-22-aa--a-launch-requirement-not-a-follow-up)). The glyph carries it.
- An item near zero will flip sign often. That is honest — it genuinely is a coin flip — and the UI must not dramatise it. No arrows, no "now positive!", no animation on a sign change.

`[INVARIANT]` **Never impose a rating floor.** Clamping breaks conservation and silently distorts every rating above it. Negative ratings are now a designed feature, not a defect to suppress. (The EGF candidate's `R_FLOOR` is a numerical safety net specific to that system's unbounded `con(r)` as `r → −∞`, and it must be moved well below zero if Candidate C is chosen at all.)

`[INVARIANT]` **Never test a rating for truthiness.** `if item.rating:` is `False` at exactly zero, which is now both a legal and a *meaningful* value. Use explicit `is None` checks. This is a real footgun introduced by this decision and it is called out here so it is caught in review rather than in production. A lint rule enforces it in `rating/`, `battles/` and `public/`.

### 10.5 Ranked and unranked — what RD buys the product

With Glicko, the leaderboard rule becomes principled instead of arbitrary:

- An item is **ranked** once `RD < RANKED_RD` (default 100 — roughly 10–20 battles). It appears in `/rankings` and gets a rank number.
- An item is **unranked** until then. Its own page exists and says so, in the product's voice: **"Still settling. 7 picks in."** It battles normally and its rating moves normally; it simply has no rank yet.

This replaces `RANKINGS_MIN_BATTLES` with something derived rather than guessed, and it is honest: the site is saying *we don't know yet*, which is true. Rank and display both use the plain rating value — no conservative `r − 2·RD` sorting, because two different numbers for one quantity confuses everyone and RD-gating already solves the problem it would solve.

Under Candidates B and C, `RANKINGS_MIN_BATTLES` (default 5) comes back as the substitute.

### 10.6 Simulation — the decision procedure

The harness from the original spec is unchanged in shape; it now compares **systems**, not just parameter sets. Assign each synthetic item a latent quality `q ~ N(0,1)`; generate outcomes from a ground-truth Bradley–Terry model `P(i beats j) = σ(λ(q_i − q_j))`; run the **real** matchmaker and the **real** rating system; model continuous item arrival and a share of purely random picks (`[CONFIG]`, default 15%, because people do pick absurd pairs on a whim).

**Scenarios** (all seeded, deterministic, run in CI):

| # | Scenario | Tests |
|---|---|---|
| S1 | 1,000 items, 1,000,000 battles, no arrivals | Convergence and steady state |
| S2 | Continuous arrivals: +50 items / 10,000 battles | Inflation and newcomer dynamics |
| S3 | Heavy-tailed attention: 10% of items get 80% of battles | **Sparse-data items — where Glicko should win** |
| S4 | 100% random matchmaking | Worst case for neighbourhood selection |
| S5 | 100% neighbourhood matchmaking | Rating-cluster lock-in |
| S6 | Adversarial: one item always loses, one always wins | Divergence behaviour |
| S7 | 10 items, 100 battles | Cold start with a tiny catalogue |
| **S8** | **50% of new items are duplicates of existing ones** | **Phase 3 pre-check: do near-identical items get near-identical ratings?** |

**Gates** — restated to be system-agnostic, since two candidates have no ceiling:

| Gate | Requirement |
|---|---|
| `GATE-R1` | Spearman ρ between final rating and true quality ≥ 0.85 (S1), ≥ 0.80 (S2), **≥ 0.70 (S3)** |
| `GATE-R2` | No `NaN`, no `inf`, no domain error, in any scenario. For Candidate C only: the clamp fires **zero** times. |
| `GATE-R3` | Mean population rating drift over the final 20% of S2 is under `[CONFIG: MAX_DRIFT_PER_10K = 5]` points |
| `GATE-R4` | P99 − P1 spread ≥ 800 points at steady state in S1 — the leaderboard must be legible, not compressed |
| `GATE-R5` | Top-20 rank churn in the final 10% of S2 is between 1% and 30% per 10,000 battles — alive, but not chaos |
| `GATE-R6` | A new item reaches its final rank decile within `[CONFIG: 30]` battles in S2 |
| `GATE-R7` | **Calibration:** bucket predicted win probabilities into deciles; observed frequency must be within **3 percentage points** of predicted in every decile with ≥1,000 samples |
| `GATE-R8` | **Leaderboard integrity:** no item in the top 20 at any point in S2 has fewer than 10 battles (Glicko: `RD ≥ RANKED_RD`) |
| `GATE-R9` | **Sign agreement:** ≥ 85% of ranked items in S1 and S2 have a rating whose sign matches the sign of `wins − losses`. **Reported as a percentage, not just pass/fail — the number decides the product's copy** ([§10.4](#104-zero-is-the-origin-and-the-sign-is-the-product)). |

`GATE-R7` is the gate that actually tells you whether the system is *right* rather than merely stable, and it is the one most likely to separate the three candidates. `GATE-R3` is where EGF-faithful is expected to fail. `GATE-R1` on S3 and `GATE-R8` are where Glicko is expected to win. `GATE-R9` does not select a system — **it selects the product's vocabulary.**

A rough Elo sanity check over 300 items and 300,000 battles put sign agreement at **~93% under the specified 50/35/15 matchmaking mix**, with the population mean pinned at exactly 0 and a spread of roughly −730 to +900. Two things to carry from that, and one not to:

- The threshold is reachable, so the plain-language copy is probably safe. Confirm it, do not assume it.
- The zero-mean and spread results support [§10.4](#104-zero-is-the-origin-and-the-sign-is-the-product) and comfortably clear `GATE-R4`.
- **Do not assume more randomness helps.** The obvious prediction — that raising the `RANDOM` weight raises sign agreement, since neighbourhood matching compresses records toward 50% — did not hold in that check (a random-heavy mix scored slightly *lower*, and neighbourhood-only scored about the same). The differences were within the noise of a single-seed run, so the honest position is that the relationship is not obvious and must be **measured across mixes by the real harness**, not reasoned about.

**Output:** `docs/RATING-SYSTEM.md` — the chosen system, its parameters, the full comparison table across all three candidates and eight scenarios, and prose explaining what would make you want to change it. **If no candidate passes, continue the parameter search within the three systems. Do not invent a fourth.**

### 10.7 Edge cases

| Case | Behaviour |
|---|---|
| Both items identical rating and RD | `E = 0.5` exactly. Symmetric and deterministic. |
| Enormous rating gap | `E` approaches 0 or 1 but never reaches it; assert `0 < E < 1`. Elo/Glicko are unbounded, so no domain error is possible — this is a genuine advantage over Candidate C. |
| An item's very first battle | No special case. `INITIAL_RD = 350` *is* the provisional mechanism. |
| RD floor reached | `RD_MIN` clamps. Unlike a rating clamp this is part of the model, not a safety net — it prevents an item becoming so "certain" it can never move again. |
| Simultaneous battles on one item | Serialised by `FOR UPDATE`. Each transaction reads a fresh `(rating, RD)` snapshot. |
| Duplicate submission | Blocked by the state machine ([§9.4](#94-battle-completion--the-atomic-transaction)); `rating_events_battle_item_uq` is the last line of defence. |
| System or parameter change | Old rows keep their `rating_system_version`. **No retroactive recomputation in MVP.** A future recompute job can replay `rating_events` in `created_at` order, because every input — including both RDs — is stored. |
| An item deleted / hidden | Ratings and events survive. It leaves matchmaking and rankings. Opponents' histories are untouched. |
| Floating point | `float64` throughout; `NUMERIC(10,4)` at the storage boundary. Round once, on write. |
| `RD` on a system that has none | Elo and EGF report a constant `INITIAL_RD` and ignore it. The column is never null, so downstream code needs no branches. |
---

## 11. Matchmaking

**`[INVARIANT]` Matchmaking knows nothing about rating computation, and rating computation knows nothing about matchmaking.** They are separate modules with a `(item_a, item_b)` tuple between them. This is what allows the strategy to be tuned aggressively without any risk to rating correctness.

### 11.1 Strategy mix

Every battle picks a strategy by weighted random draw. Weights are `[CONFIG]` and must sum to 1.0.

| Strategy | Default weight | Behaviour |
|---|---:|---|
| `NEIGHBOURHOOD` | 0.50 | Pick a seed item, then an opponent whose rating is within `±[CONFIG: NEIGHBOUR_BAND = 150]`. Widen the band up to 4× if nothing is found. |
| `RANDOM` | 0.35 | Two uniformly random approved items. **This is the fun.** `[P6]` |
| `COLD_START` | 0.15 | Seed from the **most uncertain** items — highest `rating_deviation` under Glicko, else `battle_count < [CONFIG: COLD_START_THRESHOLD = 20]` — opponent uniformly random. Bootstraps new items so contributions get seen and RD converges. |

The default weights encode a product judgement: **more than a third of all matchups are pure chaos on purpose.** A system tuned only for rating efficiency would set `RANDOM` to ~0 and would be correct and boring. Do not let a later optimisation pass "fix" this — the weight is a product decision, and the acceptance test in M4 asserts `RANDOM_WEIGHT ≥ 0.25`.

Seed override: when `GET /api/battles/current?seed={item_id}` is supplied from the "Add one" flow, that item becomes the seed and strategy `RANDOM` selects the opponent. The seed is validated (exists, `APPROVED`, not the same as the opponent) and used once.

### 11.2 Eligibility filters

Applied to both items, always:

- `status = 'APPROVED'`
- `item_a_id <> item_b_id`
- The user has **not** produced a `COMPLETED` battle on this comparison within `[CONFIG: USER_PAIR_COOLDOWN_DAYS = 30]`
- The user has not seen this comparison in their last `[CONFIG: USER_RECENT_PAIRS = 50]` battles (covers skips and expiries too)
- Neither item appeared in the user's last `[CONFIG: USER_RECENT_ITEMS = 8]` battles (prevents "carbonara again?" fatigue)

Down-weighting (not exclusion):

- Items created by the requesting user are eligible but drawn at `[CONFIG: OWN_ITEM_WEIGHT = 0.5]` relative weight. A creator should see their item, but should not be an efficient way to move its rating. Combined with the fact that the user cannot choose the matchup, this makes self-inflation impractical. Monitoring backs it up ([§13.6](#136-guest-play-and-anti-abuse)).

`matchmaking/` reads `items.rating_deviation` as an ordinary column. `[INVARIANT]` It still never imports `rating/` and never computes a rating or a deviation.

### 11.3 Implementation

MVP scale (up to ~100k approved items) is served by direct SQL against `items_pool_idx`. Keep it simple:

```sql
-- NEIGHBOURHOOD, second leg
SELECT id FROM items
WHERE status = 'APPROVED'
  AND id <> :seed_id
  AND rating BETWEEN :lo AND :hi
  AND id <> ALL(:recent_item_ids)
ORDER BY random()
LIMIT 1;
```

`ORDER BY random()` over a rating-banded subset is fine at this scale. For the `RANDOM` strategy, avoid a full-table sort using the standard "random offset" trick against a cached approved-item count refreshed every 60s:

```sql
SELECT id FROM items WHERE status = 'APPROVED' OFFSET floor(random() * :approved_count) LIMIT 1;
```

**Scale trigger `[CONFIG]`:** when `p95(matchmaking_duration_ms) > 40ms` or approved items exceed 250,000, replace this with an in-memory sampled pool in the API process refreshed every 60s. Not before. `[P7]`

Retry policy: up to `[CONFIG: MATCHMAKING_ATTEMPTS = 5]` attempts, relaxing the cooldown filters one at a time (recent items → recent pairs → pair cooldown). If all fail, fall back to pure `RANDOM` with only the `APPROVED` + distinct filters. If *that* fails, return `503 no_items_available`.

### 11.4 Cold start and the catalogue floor

The catalogue cannot start empty — an empty game is not a game. Seed items are curated by hand before launch ([Q9](DECISIONS.md)); the loader and the warm-up run are M7's job.

**How many are actually needed.** With `N` approved items there are `N(N−1)/2` distinct pairs, and each actor is filtered against their own cooldowns, so exhaustion is a *per-actor* limit, not a global one:

| `N` | distinct pairs | sessions before an actor starts repeating (at 12 picks/session, 30-day cooldown) |
|---:|---:|---|
| 20 | 190 | ~16 — and `USER_RECENT_ITEMS = 8` leaves only 12 items to draw from, so it feels repetitive within minutes |
| 50 | 1,225 | ~100 |
| 100 | 4,950 | ~400 |
| 300 | 44,850 | effectively unbounded |

**The binding constraint is not arithmetic, it is comedy.** The absurdity comes from *category diversity*, not from item count: sixty items spread across food, weather, chores, days, sensations, objects, places, activities and abstractions produce far funnier pairs than three hundred foods. A catalogue that is 80% one domain generates sensible matchups, and sensible matchups are the failure mode. `[P6]`

**Recommendation: at least 50 to launch, 150–300 preferred, spread across at least 8 domains with no domain above 20%.** Below ~50, `MATCHMAKING_ATTEMPTS` exhausts and heavy players will see `503 no_items_available` within their first session — so if the launch list is short, drop `USER_PAIR_COOLDOWN_DAYS` and `USER_RECENT_ITEMS` proportionally and raise them as the catalogue grows. Both are already config values; M7 sets them from the actual seed count rather than from the defaults.

Seed items are created by a system user, `APPROVED`, and marked `source = 'seed'`. They are ordinary items in every other respect and compete on the same leaderboard.

### 11.5 Explicitly out of scope for MVP

Category awareness, semantic similarity, user preference modelling, per-user difficulty tuning, exploration/exploitation bandits, information-gain-maximising selection. All of these make the matchups *better* and the product *worse*. `[P6]`

---

## 12. Moderation

### 12.1 Pipeline

```
raw user input
   ↓  normalisation           (deterministic, pure, unit-testable)
   ↓  structural validation   (length, charset, shape)
   ↓  deduplication           (unique index on normalized_text)
   ↓  hard blocklist          (pre-filter only — NOT the mechanism)
   ↓  moderation provider     (pretrained model/API)
   ↓  policy decision         (scores → thresholds → decision)
   ↓  APPROVED / REVIEW / REJECTED
```

### 12.2 Normalisation

Deterministic and pure. Two functions, both heavily unit-tested:

```
display_text(raw):
    NFC normalise
    strip leading/trailing whitespace
    collapse internal whitespace runs to a single space
    strip zero-width characters (U+200B–U+200D, U+FEFF) and bidi controls (U+202A–U+202E, U+2066–U+2069)
    reject if any C0/C1 control remains
    → stored in items.text, shown to users

normalized_text(display):
    casefold()
    NFKD normalise, strip combining marks (café → cafe)
    strip all punctuation and symbols
    collapse whitespace
    → stored in items.normalized_text, UNIQUE
```

`normalized_text` is a **crude, conservative** dedupe key — exact-ish matches only. "Carbonara" and "Spaghetti Carbonara" are deliberately different items in MVP. Merging them is Phase 3 and requires semantic similarity plus community confirmation. Do not attempt fuzzy dedupe now; a false merge is unrecoverable.

### 12.3 Structural validation

| Rule | Value |
|---|---|
| Length | **2–64 characters** after normalisation `[CONFIG: ITEM_MAX_LENGTH = 64]` |
| Lines | Exactly one; newlines rejected |
| No URLs, emails, phone numbers, `@handles` | Regex reject → `invalid_text` |
| Not majority digits or punctuation | Reject |
| Not a single repeated character | Reject |
| Unicode scripts | MVP restricts to Latin + common punctuation + digits `[CONFIG: ALLOWED_SCRIPTS]`. Phase 4 lifts this. |
| Reserved slugs | `api, admin, play, add, rankings, item, compare, login, register, about, terms, privacy, sitemap, robots, og, _next, static` |

**Why 64.** It is one character longer than 63 and one shorter than 65, it is a power of two, and it comfortably fits every item anyone has actually proposed (*"Fitting bed sheets"* is 18, *"Spaghetti alla Carbonara"* is 24, *"300 W FTP"* is 9). Past roughly 48 characters an item starts reading as a sentence rather than a thing, which is why the counter appears there as a nudge rather than a wall.

If a user asks why the limit is 64, the answer — in the About page, in support, and in the counter's tooltip — is exactly this:

> **Why 64 characters?**
> That's why.

`[CONFIG]` The limit can be *raised* later without pain. It can never be *lowered* without orphaning existing items, so 64 is a ceiling, not a starting point.

### 12.4 Provider

`ModerationProvider` is a protocol with three implementations:

```python
class ModerationProvider(Protocol):
    async def check(self, text: str) -> ProviderResult:
        """→ ProviderResult(scores: dict[str, float], model: str, raw: dict)"""
```

| Implementation | Use |
|---|---|
| `OpenAIModerationProvider` | **Primary.** `omni-moderation-latest`. Free, low latency, well-calibrated multi-category scores. |
| `HeuristicProvider` | Fallback + local dev + tests. Blocklist and pattern scores only. Never used in production as the primary. |
| `NullProvider` | Test fixtures only. Approves everything. Guarded so it can never be selected when `ENV=production`. |

Alternatives if the primary is unavailable or policy forbids external calls: Google Perspective API, or a locally-hosted `unitary/toxic-bert` / Detoxify model behind the same protocol. The interface exists precisely so this is a config change.

`[INVARIANT]` **No keyword blocklist is ever the sole decision mechanism.** The blocklist is a pre-filter for unambiguous slurs and known-bad strings; everything that passes it still goes to the model.

### 12.5 Policy

Configuration maps provider category scores to a decision, versioned as `policy_version`:

```python
POLICY_V1 = {
  "reject_at":  {"sexual/minors": 0.10, "hate/threatening": 0.20, "violence/graphic": 0.60,
                 "harassment/threatening": 0.30, "self-harm": 0.30, "sexual": 0.70, "hate": 0.50},
  "review_at":  {"sexual/minors": 0.02, "hate/threatening": 0.05, "violence/graphic": 0.30,
                 "harassment/threatening": 0.10, "self-harm": 0.10, "sexual": 0.40, "hate": 0.25},
  "default": "APPROVED",
}
```

Decision: any category ≥ its `reject_at` → `REJECTED`. Else any ≥ `review_at` → `REVIEW`. Else `APPROVED`.
Named-person detection (targeting a private individual) has no provider category; MVP handles it via the blocklist plus the report queue, and it is an explicit limitation recorded in the runbook.

**Synchronous, in-request.** The provider call happens inside `POST /api/items` with a `[CONFIG: MODERATION_TIMEOUT_MS = 2500]` timeout, because "Added." must feel instant and the user is right there. Consequences:

- Provider timeout or error → decision `ERROR`, item status `REVIEW`, response `202` with *"Added. We'll take a quick look before it joins."* The user is never blocked by our vendor's availability, and nothing unmoderated ever becomes public.
- The `moderation_results` row is written in the same transaction as the item.
- Circuit breaker: `[CONFIG: 10]` consecutive provider failures opens the breaker for 60s; all items go to `REVIEW` while it is open, and an alert fires.

**Rejection copy is deliberately vague** — *"We can't add that one."* No category, no score, no explanation. Detailed rejection reasons are a free classifier-probing oracle for anyone trying to find what gets through.

### 12.6 Admin review

The smallest thing that works. A server-rendered, admin-only surface (FastAPI + Jinja, or `sqladmin`) with three screens:

1. **Queue** — items in `REVIEW` or `PENDING_MODERATION`, oldest first, with text, provider scores, creator, creation time.
2. **Decision** — Approve / Reject buttons. Writes a new `moderation_results` row with `reviewed_by_user_id`, updates `items.status`, sets `published_at` on approval.
3. **Reports** — open `item_reports` grouped by item, with the same two buttons.

Not a product. No dashboards, no analytics, no bulk tooling, no roles beyond `is_admin`. Every admin action is written to `moderation_results` (append-only) — admin actions are auditable by construction.

Auto-hide: an item reaching `[CONFIG: AUTO_HIDE_REPORT_COUNT = 5]` distinct reports is set to `HIDDEN` immediately and queued for review. Hidden items leave matchmaking and rankings; their pages return `410` and drop out of the sitemap on the next build.

**Scope of reporting in MVP ([Q5](DECISIONS.md)):** users report **items**, and only items, and only from an item page — never from inside the loop, because a report button next to the cards is a second primary verb and a way to avoid deciding. `[P1]` `[P2]`

Reporting a **bad pair** or a **near-duplicate** is deliberately future work. Until then both are *inferred* rather than reported, at zero UI cost, from data the loop already produces:

- A **comparison** with an unusually high `skip_count / battle_count` is a bad pair.
- An **item** with a high skip rate across many *different* opponents is a bad item — unclear, meaningless, or something moderation missed — and belongs in the review queue automatically.
- Two items that are near-duplicates produce near-identical rating trajectories and a comparison between them with a ~50/50 split and a high skip rate. That signal is exactly what Phase 3's candidate generation will consume, which is why `GATE-R8`'s sibling scenario `S8` exists in the rating simulation ([§10.6](#106-simulation--the-decision-procedure)).

Both inferences are SQL over `battles` and `comparisons`, need no new UI, and can ship as admin-queue feeds whenever they earn their place.

### 12.7 Rate limits on creation

`[CONFIG]` `20` items/user/day, `5`/user/hour, `50`/IP/day. Verified email required. New accounts (< 24h old) capped at `5`/day.

---

## 13. Security and anti-abuse

### 13.1 Authentication

| Concern | Decision |
|---|---|
| Password hashing | **Argon2id** via `argon2-cffi`. `time_cost=3, memory_cost=64MiB, parallelism=4` `[CONFIG]`, tuned so hashing takes 150–300ms on production hardware. Rehash on login when parameters change. |
| Password rules | Minimum 10 characters. No composition rules. Check against a top-10k common-password list. No forced rotation. |
| Sessions | Opaque 32-byte random token, **SHA-256 hashed at rest** in `sessions.token_hash`. Cookie `httpOnly; Secure; SameSite=Lax; Path=/`. Sliding expiry `[CONFIG: 30 days]`, absolute cap `[CONFIG: 180 days]`. |
| Why not JWT | Sessions must be revocable on password reset and on logout, the frontend is server-rendered on the same origin, and there is no third-party API consumer. A stateless token buys nothing here and costs revocability. `[P7]` |
| Session fixation | A new session id is issued on login and on password change. |
| Logout | Sets `revoked_at`; the cookie is cleared. Revocation is checked on every request. |
| Password reset | 32-byte token, SHA-256 stored, single-use (`used_at`), TTL `[CONFIG: 60 min]`. Confirming a reset revokes **all** the user's sessions. |
| Email verification | Same token mechanics, TTL `[CONFIG: 24h]`, resendable at 3/hour. |
| Enumeration | Registration, login and reset return responses that do not distinguish "unknown email" from other outcomes. Login failure is a constant-time comparison against a dummy hash when the user does not exist. |
| Admin | `is_admin` flag, granted only by direct SQL. No self-service, no invitation flow, no admin UI for granting admin. |

### 13.2 Transport and headers

HSTS (`max-age=63072000; includeSubDomains; preload`), TLS 1.2+, HTTP→HTTPS redirect at the edge.
`Content-Security-Policy` with no `unsafe-inline` for scripts (nonce-based for the Next.js hydration script), `default-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`, `base-uri 'self'`.
`X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` denying camera/microphone/geolocation/payment.

### 13.3 CSRF

Cookie auth means CSRF is real. Three layers:

1. `SameSite=Lax` on the session cookie (blocks cross-site `POST` entirely).
2. Double-submit token: `X-PickOne-CSRF` header must match an HMAC of the session's `csrf_secret`. Enforced by middleware on every unsafe method — **default-deny**, with an explicit allowlist for `/api/auth/login` and `/api/auth/register` (which have no session yet).
3. Strict `Origin`/`Referer` check on unsafe methods; mismatch → `403`.

`GET /api/battles/current` reads the actor's standing pair and lazily re-establishes it if absent ([§9.3](#93-the-standing-pair-invariant)). It is idempotent within the TTL and a forged cross-site `GET` achieves nothing beyond changing which pair the victim sees next. It stays a `GET`. **Re-open this the moment the standing pair gains a cost** — a rate-limit charge, a notification, a paid resource — at which point it becomes `POST /api/battles` with the `GET` retained as a pure read.

**A guest is created by that same `GET`**, which means a cross-site request can create a guest row. That is a resource-consumption concern, not a security one, and it is handled by the rate limiter and the janitor ([§13.6](#136-guest-play-and-anti-abuse)), not by CSRF.

### 13.4 Rate limits

Fixed-window counters in Postgres (`rate_limits`), keyed by user id and/or hashed IP. Every limit is `[CONFIG]`.

| Endpoint | Limit |
|---|---|
| `POST /auth/register` | 5/hour/IP, 20/day/IP |
| `POST /auth/login` | 10/15min/IP, 5/15min/account (then exponential backoff, max 15 min) |
| `POST /auth/password-reset/request` | 3/hour/email, 10/hour/IP |
| `POST /auth/verify/resend` | 3/hour/user |
| `POST /items` | 5/hour/user, 20/day/user, 50/day/IP |
| `GET /battles/current` | 90/min/actor, **and 300/hour/IP for guest creation** |
| `POST /battles/*/pick` and `/skip` | 150/min/actor |
| `POST /items/*/report` | 20/day/user (registered only) |
| Public `GET` (rankings/item/comparison) | 300/min/IP, served mostly from CDN anyway |

`[CONFIG]` **Switch to Redis when** the API runs more than 4 processes *or* p95 rate-limit check latency exceeds 5ms. Not before. `[P7]`

### 13.5 Authorisation and validation

- Every battle mutation re-derives the owner from the session. Nothing about ownership is ever read from the request body.
- Wrong owner → `404`, not `403`.
- All input through Pydantic v2 models with explicit `max_length`; no `dict[str, Any]` request bodies anywhere.
- All SQL through SQLAlchemy with bound parameters. No string-interpolated SQL, no `text()` with f-strings — enforced by a lint rule.
- Output escaping is React's default; `dangerouslySetInnerHTML` is banned by ESLint rule with no exceptions. Item text is user content and is rendered as text everywhere, including in `<title>`, meta tags, JSON-LD (where it must be JSON-encoded, not string-concatenated) and OG images.

### 13.6 Guest play and anti-abuse

Opening play to anonymous visitors ([Q1](DECISIONS.md)) removes the registration wall from the funnel and hands the abuse problem a much wider door. Both are true, and the mitigations below are what make the trade acceptable.

**The structural defence is the product itself: a user cannot choose which pair they are shown.** To move a specific item you must be dealt it, which is random and rare. Sybil accounts do not help you target anything — they only let you cast more *random* votes. That is a fundamentally weaker attack than it looks, and it is why guest play is defensible here in a way it would not be on a conventional polling site.

| Vector | Mitigation |
|---|---|
| **Guest-row flooding** (crawlers, scripts, cross-site `GET`s) | Guests are created only by `GET /api/battles/current`, rate limited to `[CONFIG: 300]`/hour/IP. A guest row is ~100 bytes. The **janitor job** deletes guests with zero completed battles and `last_seen_at` older than `[CONFIG: GUEST_EMPTY_TTL_DAYS = 7]`. This is a disk-space problem with a `DELETE` for a solution, not a security incident. |
| **Ballot stuffing via many guest identities** | Each identity still gets random pairs, so N identities buy N random votes, not N targeted ones. Per-IP limits on both guest creation and picks. The share-of-a-comparison monitor below catches concentrated effort. |
| **Targeted inflation of one's own item** | Item creation requires a **verified registered account** — the one hard gate in the product. Combined with `OWN_ITEM_WEIGHT = 0.5` down-weighting and random matchmaking, moving your own item requires being dealt it, repeatedly, by chance. |
| **Scripted rapid picking** | Rate limits; `decision_ms` recorded; picks-per-actor-per-hour monitored. **MVP records and alerts; it does not auto-block** — false positives on genuinely fast players cost more than the abuse. |
| **Coordinated brigading of one comparison** | Monitor the share of a comparison's battles originating from one actor or one /24. Alert above `[CONFIG: 20%]` with ≥50 battles. Manual response in MVP. |
| **Spam item flooding** | Creation rate limits, moderation, dedupe index, verified-account gate. |
| **Scraping** | Public data is public and meant to be crawled. Rate limit by IP, let the CDN absorb it, and do **not** deploy aggressive bot blocking — it would hurt search crawlers, which are the growth engine. |

**The escape hatch, specified now so it is not improvised later.** Every battle's actor is recoverable, and `is_guest` is on the `users` row, so the influence of guest picks is *measurable* and — if it ever proves toxic — *reversible*: `rating_events` is complete and append-only, so ratings can be recomputed over the subset of battles from registered users only. This is a real, tested capability in the reconciliation job's toolkit, not a hope. It is also the fallback if the metrics in [§15.3](#153-the-metrics-that-matter) show guest picks behaving materially differently from registered ones — which is itself a monitored metric, precisely so the question is answered with data.

**Auditability `[INVARIANT]`:** every rating point is traceable. `rating_events` is append-only (the application role has no `UPDATE`/`DELETE` grant on it) and every row carries the battle, the actor, the opponent, both ratings, both deviations, the system-specific terms and the system version.

### 13.7 Account deletion and the audit trail

> **Resolving Q8.** *"Deleting a user must remove all their personal information; their battles become stale, though they must still count to the total."* Implemented literally.

`POST /api/me/delete` performs a **hard delete of the person, and a permanent preservation of their effect on the world.**

```
BEGIN
  expire any PENDING battle for this user          -- keeps the partial index clean
  revoke all sessions; delete all email_tokens
  UPDATE items          SET created_by_user_id = NULL WHERE created_by_user_id = :uid
  UPDATE item_reports   SET reporter_user_id   = NULL WHERE reporter_user_id   = :uid
  UPDATE analytics_events SET user_id = NULL          WHERE user_id = :uid
  DELETE FROM users WHERE id = :uid                -- battles.user_id → NULL via ON DELETE SET NULL
COMMIT
```

What is destroyed: the email, the password hash, the session and token rows, the settings, the link between a human being and anything they did. **The `users` row itself is gone** — not anonymised-in-place, because a surviving row with a stable id still links every action to one identity and is still pseudonymous personal data.

What survives, deliberately and permanently:

- Every `battles` row, with `user_id = NULL` meaning *"the actor is gone"*.
- Every `rating_events` row — untouched, since it never referenced a user.
- Every rating, and every denormalised counter on `items` and `comparisons`.

**Their picks still count.** A rating is the collective output of everyone who ever played; removing one person's contributions would retroactively rewrite a public, shared artefact that other people's picks were measured against. The battles go stale — unattributable, ungroupable, no longer usable for per-user analytics — but they never stop counting.

Consequences to handle honestly:

- **The privacy policy must say this in a sentence a person can read**, not in a schedule: *"If you delete your account we erase everything that identifies you. The picks you made stay part of the rankings, with nothing linking them to you."* This is a launch blocker, not a nicety.
- Per-user analytics silently lose deleted actors. Session and cohort views must therefore tolerate `user_id IS NULL` rather than assuming a join succeeds — a test asserts this.
- The reconciliation job must not treat a `NULL` actor as corruption.
- **Guests get the same treatment on reaping.** A guest that never completed a battle is deleted outright; a guest with battles is deleted after `[CONFIG: GUEST_MAX_AGE_DAYS = 180]`, leaving its battles with a `NULL` actor exactly as above.

### 13.8 Privacy and data handling

- Store hashed IPs (`HMAC-SHA256` with a server-side pepper), never raw, and only on `sessions` and rate-limit keys.
- Email is the only PII. No tracking pixels, no third-party analytics scripts that fingerprint. `[Phase 5 ads will change this — it is called out in the Phase 5 brief.]`
- Account deletion: see [§13.7](#137-account-deletion-and-the-audit-trail).
- A guest's only stored data is a session cookie, a hashed IP and their picks. Guests are told this in one line on `/play` linking to the privacy policy — no banner, no modal.
- No data is sold, shared, or sent anywhere except the moderation provider (item text only) and the email provider (email address only). Both are named in the privacy policy.

---

## 14. SEO architecture

SEO is how PickOne is discovered. The mechanism is simple and compounding: **every pair that gets played becomes a permanent page that gets better as it is played more.** The engineering job is to make those pages genuinely good and to stop the system from generating millions of empty ones.

### 14.1 The indexable entity graph

```
    /                      hub — the game + real content below the fold
    │
    ├── /rankings          hub — the full ordered list, paginated
    │       │
    │       └── /item/{slug}          leaf-hub — one thing
    │               │
    │               ├── links to its closest rivals ──┐
    │               ├── links to its biggest wins ────┤
    │               └── links to its recent opponents ┤
    │                                                 ▼
    └────────────────────────────── /compare/{a}-vs-{b}   leaf — one relationship
                                            │
                                            └── links back to both /item/ pages
```

Two entity types generate pages. Items are created by users; comparisons are created by *play*. This is the growth loop: play produces pages, pages produce traffic, traffic produces play.

### 14.2 Rendering strategy

| Route | Rendering | Cache |
|---|---|---|
| `/` | SSR (SSG shell + dynamic teaser) | `s-maxage=300, stale-while-revalidate=3600` |
| `/rankings`, `/rankings/page/{n}` | ISR, revalidate 300s | `s-maxage=300, swr=3600` |
| `/item/{slug}` | ISR, revalidate 900s, on-demand revalidation on significant change | `s-maxage=900, swr=86400` |
| `/compare/{slug}` | ISR, revalidate 900s | `s-maxage=900, swr=86400` |
| `/play`, `/add`, auth pages | CSR shell, `noindex` | `no-store` |
| `/og/**` | On-demand image generation, immutable per content hash | `s-maxage=31536000, immutable` |
| `/sitemap*.xml` | Generated by the worker every `[CONFIG: 6h]`, served from storage | `s-maxage=3600` |

`[INVARIANT]` **No public page requires JavaScript to show its content.** A crawler with JS disabled must see the full item text, ratings, counts, and all internal links. The interactive battle may be client-side; nothing else may be.

**The `/` compromise, and what guest play changes.** The home page must be both the game and a content page. Resolution:

- Above the fold: the two cards. The server renders a **cached featured comparison** — real item text, real names, no JavaScript required — so a crawler sees genuine content instantly. On mount, the client calls `GET /api/battles/current` and swaps in a real, live battle for *any* visitor, guest or registered.
- **A crawler must not cause a guest row and a battle to be created**, and with guest play this no longer holds automatically. Three layers, in order of reliability:
  1. `robots.txt` disallows `/api/`, so a well-behaved crawler never calls the endpoint even while rendering.
  2. Guest creation is rate limited per IP ([§13.4](#134-rate-limits)); crawler fleets hit it long before they matter.
  3. The janitor reaps guests with zero completed battles after 7 days ([§13.6](#136-guest-play-and-anti-abuse)).
  A JS-rendering crawler that ignores `robots.txt` will still create some guest rows. That is acceptable: the cost is bytes, the rows are reaped, and no rating is affected because a crawler never picks. **Do not add bot fingerprinting to prevent it** — the false-positive risk to real users and to Googlebot vastly exceeds the storage cost. `[P7]`
- Below the fold, server-rendered: what PickOne is (two sentences), the current top 10 with links, the most-played comparisons this week with links, and today's newest items. This makes `/` a genuine hub page that passes crawl equity to the leaves, and it gives the home page a reason to be re-crawled often.

### 14.3 URL and slug strategy

| Pattern | Example |
|---|---|
| Item | `/item/carbonara` |
| Comparison | `/compare/carbonara-vs-fitting-bed-sheets` |
| Rankings | `/rankings`, `/rankings/page/2` |

Rules:

- Lowercase, ASCII, hyphen-separated, no trailing slash, no query parameters that change content (page number is a path segment, not `?page=`).
- **Item slug** = `slugify(text)`, truncated to 64 chars at a word boundary. On collision, append `-2`, `-3`, … up to `-99`; beyond that, append a 6-char base32 hash. Generated inside the insert transaction; a unique-violation retries with the next suffix (bounded loop, then hash).
- **Comparison slug** = `{slug_a}-vs-{slug_b}` where `a`/`b` follow the **database canonical order** (`item_a_id < item_b_id`), not alphabetical order. Rationale: the DB order is stable forever and independent of text, so the URL never has to change. Alphabetical order would be prettier and would break if an item were ever renamed.
- The literal token `-vs-` is reserved: an item slug that would contain `-vs-` gets it replaced with `-versus-` at slug generation, so comparison slugs can never be ambiguously parsed.
- **Reversed order → `301`** to the canonical slug. Trailing slash, uppercase, and index-file variants also `301`.
- **`404`, not a generated page**, for `/compare/x-vs-y` where the comparison row does not exist. There is no route that materialises a page for an unplayed pair. This one rule is what prevents `n(n−1)/2` thin pages.
- Slugs are **immutable**. Items are immutable in MVP (§3.2), so this is free. When Phase 3 introduces merging, the losing item's slug `301`s to the survivor and an `item_slug_aliases` table records it — that table's existence is anticipated now but not created.

### 14.4 Indexing thresholds — the anti-thin-content mechanism

A page exists (is reachable, renderable, useful) long before it deserves to be indexed. Two separate gates:

| Page | Rendered? | `index,follow`? | In sitemap? |
|---|---|---|---|
| `/item/{slug}`, `battle_count < [CONFIG: ITEM_INDEX_MIN_BATTLES = 5]` | yes | **no** — `noindex,follow` | no |
| `/item/{slug}`, `battle_count ≥ 5`, `APPROVED` | yes | yes | yes |
| `/item/{slug}`, `HIDDEN`/`REJECTED` | `410 Gone` | — | removed |
| `/compare/{slug}`, `battle_count < [CONFIG: COMPARISON_INDEX_MIN_BATTLES = 10]` | yes | **no** — `noindex,follow` | no |
| `/compare/{slug}`, `battle_count ≥ 10` | yes | yes | yes |
| `/compare` where either item is not `APPROVED` | `410 Gone` | — | removed |
| `/rankings/page/{n}`, `n ≤ [CONFIG: RANKINGS_INDEX_MAX_PAGE = 100]` | yes | yes | yes |
| `/rankings/page/{n}`, `n > 100` | yes | `noindex,follow` | no |
| `/play`, `/add`, `/login`, `/register`, `/verify`, `/reset`, `/admin` | yes | `noindex,nofollow` | no |

`noindex,**follow**` is deliberate: a below-threshold page still passes crawl equity to the item pages it links to. Never `noindex,nofollow` on a content page.

Thresholds are configuration and will be tuned after launch against Search Console data. The initial values are conservative on purpose: it is far cheaper to raise a threshold than to recover from a thin-content demotion.

### 14.5 Metadata

Every public page emits, server-side:

```html
<title>Carbonara vs Pizza — who wins? | PickOne</title>
<meta name="description" content="8,421 people picked. Carbonara wins 61% of the time against Pizza. Pick one yourself on PickOne.">
<link rel="canonical" href="https://pickone.app/compare/carbonara-vs-pizza">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:type" content="website">
<meta property="og:title" content="Carbonara vs Pizza">
<meta property="og:description" content="8,421 picks. Carbonara leads 61% – 39%.">
<meta property="og:image" content="https://pickone.app/og/compare/carbonara-vs-pizza.png">
<meta property="og:url" content="https://pickone.app/compare/carbonara-vs-pizza">
<meta name="twitter:card" content="summary_large_image">
```

Templates (all `[CONFIG]`-able strings, all with the numbers baked in so they change as data accumulates — which drives re-crawling):

| Page | Title | Description |
|---|---|---|
| `/` | `PickOne — what would you choose?` | `Two random things. Pick one. Your choice joins the world's ranking of everything.` |
| `/rankings` | `The rankings — everything, ranked by you \| PickOne` | `{n} things ranked by {m} picks. #1 right now: {top_item}.` |
| `/rankings/page/n` | `The rankings — page {n} \| PickOne` | `Ranked {from}–{to} of {n} things on PickOne.` |
| `/item/{slug}` | `{Item} — ranked #{rank} \| PickOne` | `{Item} is #{rank} on PickOne at {signed_rating}, from {battles} picks — {wins} wins, {losses} losses. See who it beats.` |
| `/compare/{slug}` | `{A} vs {B} — who wins? \| PickOne` | `{n} people picked. {Winner} wins {pct}% of the time against {Loser}. Pick one yourself.` |

**Open Graph images are generated per page** (`ImageResponse` at `/og/item/{slug}.png` and `/og/compare/{slug}.png`): the item text(s) in the product's typography, the split percentage, and the wordmark. Comparison OG images are a meaningful share driver — "Carbonara 61% / Pizza 39%" is a screenshot people send to friends. Item text must be escaped and length-capped in the image generator like anywhere else.

### 14.6 Structured data

Only where genuinely appropriate. Emitted as `application/ld+json`, JSON-encoded (never string-concatenated):

- **`BreadcrumbList`** on `/item/{slug}` (`Home → Rankings → Carbonara`) and `/compare/{slug}` (`Home → Rankings → Carbonara → Carbonara vs Pizza`). ✅
- **`ItemList`** on `/rankings` and `/rankings/page/{n}`, with `position` and `url` per entry. ✅
- **`WebSite`** on `/`. ✅ (no `SearchAction` — there is no site search in MVP, and declaring one that does not exist is a violation).

**Explicitly not used, and this is a trap worth naming:** `Product`, `Review`, `AggregateRating`. Item ratings are not product reviews; marking them up as such misrepresents the content, is against structured-data guidelines, and risks a manual action. PickOne is not a review site `[§20]` — the markup must not claim otherwise. Also excluded: `FAQPage`, `HowTo`, `Dataset`.

### 14.7 Sitemaps

```
/sitemap.xml                      ← sitemap index
  ├── /sitemaps/static.xml        ← /, /rankings, /about, /terms, /privacy
  ├── /sitemaps/rankings.xml      ← /rankings/page/1..100
  ├── /sitemaps/items-{n}.xml.gz  ← indexable items, 50,000 per file
  └── /sitemaps/comparisons-{n}.xml.gz
```

- Generated by the worker every `[CONFIG: SITEMAP_REBUILD_HOURS = 6]`, written to object storage (or a served directory), never generated per-request.
- `lastmod` from the entity's latest activity (`items.rating_updated_at`, `comparisons.last_battle_at`). Accurate `lastmod` is what makes recrawling efficient; a `lastmod` that always equals "now" is worse than none.
- No `priority`, no `changefreq` — Google ignores both.
- **Comparison sitemap is capped** at the top `[CONFIG: SITEMAP_MAX_COMPARISONS = 100,000]` by `battle_count`. Beyond that, comparisons are reachable by internal links but not pushed. This is a crawl-budget decision, and the cap rises as the site earns authority.
- Removed entities (hidden items, sub-threshold comparisons) drop out on the next rebuild and their pages return `410` immediately, which is the correct signal for fast de-indexing.

### 14.8 robots.txt

```
User-agent: *
Allow: /
Disallow: /api/
Disallow: /admin
Disallow: /play
Disallow: /add
Disallow: /login
Disallow: /register
Disallow: /verify
Disallow: /reset
Disallow: /*?
Sitemap: https://pickone.app/sitemap.xml
```

`Disallow: /*?` blocks crawling of any query-string URL. There are no content-bearing query parameters by design — pagination is a path segment and the `?seed=` parameter is authenticated-only. This kills tracking-parameter duplicates before they exist.

Staging and preview environments serve `Disallow: /` plus `X-Robots-Tag: noindex` at the edge. **This must be verified in CI** — a preview deploy that gets indexed is the classic own-goal.

### 14.9 Crawl budget, internal linking and pagination

**Internal linking is the mechanism by which comparison pages get discovered.** Each `/item/{slug}` page links to:

- Its `[CONFIG: 10]` closest rivals by rating (the most interesting comparisons)
- Its `[CONFIG: 5]` biggest wins and `[CONFIG: 5]` biggest losses
- Its `[CONFIG: 10]` most-played comparisons
- Its rank neighbours on the rankings (`#4` links to `#3` and `#5`)

All links are **plain server-rendered `<a href>`**, deduplicated, capped at `[CONFIG: MAX_INTERNAL_LINKS_PER_PAGE = 60]`. No `nofollow` on internal links. Every indexable page is within 3 clicks of `/`.

**Pagination:** each `/rankings/page/{n}` is self-canonical (never canonicalised to page 1 — that hides pages 2+ from the index). `rel="prev"`/`rel="next"` are emitted as a hint, first/last/±2 numeric links are rendered, page size 50 `[CONFIG]`.

**Crawl budget controls,** in order of importance: only real comparisons are addressable; sub-threshold pages are `noindex`; no query-parameter URLs; capped comparison sitemap; accurate `lastmod`; `410` (not `404`, not soft-404) for removed content; ISR so crawl load does not hit Postgres.

**Renaming behaviour (MVP: none).** Items are immutable, so slugs never change and no redirect infrastructure is needed. The one exception is an admin typo fix, which changes `items.text` but **never** `items.slug` — the slug stays, the page is not moved, no redirect is created. Phase 3 merging is the first thing that needs `301`s, and it will add `item_slug_aliases` at that time. Anticipate; do not build.

### 14.10 Measurement

Search Console verified at launch, sitemap submitted, and these tracked weekly: indexed page count split by type (item / comparison / other), impressions and clicks by page type, average position for `"{a} vs {b}"` queries, crawl rate and crawl errors, `410` rate, Core Web Vitals (LCP/INP/CLS) per template. **The primary SEO metric is `indexed comparison pages` and `organic sessions per indexed page`** — the second one is what tells you whether the threshold is set correctly.

---

## 15. Analytics

The one question MVP analytics must answer: **is the loop addictive?** Everything else is secondary.

### 15.1 Source of truth

`[INVARIANT]` **Core-loop metrics are computed from `battles`, never from client events.** The battles table already records every pick, skip, expiry and their timestamps — it is complete, trustworthy, and immune to ad blockers. Client-side events are used only for things the database cannot see: page views, scroll, funnel drop-off before a request is made, and UI interactions.

- **Server-derived (authoritative):** battles created / completed / skipped / expired, picks per session, decision time, items created, moderation outcomes, guest creation, guest→registered conversion, registration and verification.
- **Every core metric is segmented by `is_guest`.** This is not optional reporting detail: it is how the guest-play decision gets evaluated after launch, and it is the input to the reversibility escape hatch in [§13.6](#136-guest-play-and-anti-abuse).
- **Client-emitted** to `POST /api/events` (batched, `sendBeacon` on unload): page views, `landing_page`, `cta_clicked`, `first_card_seen`, `swipe_used`, `keyboard_used`, `add_form_opened`, `add_form_abandoned`.
- **Tooling:** PostHog (cloud or self-hosted) for exploration and funnels; the authoritative numbers come from SQL over `battles` in a small set of versioned views. If PostHog is a problem for privacy or budget, `analytics_events` plus SQL is sufficient for MVP — the design does not depend on it.

### 15.2 Session definition

A **play session** is a run of a user's battles with no gap greater than `[CONFIG: SESSION_GAP_MINUTES = 30]`. Defined once, in SQL, in a view. Every session metric derives from that view so no two numbers disagree.

### 15.3 The metrics that matter

**North star: `picks per session` (median), and `D7 return rate`.** If those two are healthy the product works; if they are not, nothing else matters.

| Metric | Definition | Launch target |
|---|---|---|
| **Picks per session** (median) | `COMPLETED` battles per play session | **≥ 12** |
| **Completion rate** | `COMPLETED / (COMPLETED + SKIPPED + EXPIRED)` | ≥ 70% |
| **Skip rate** | `SKIPPED / all resolved` | 5–20% (below 5% suggests skip is undiscoverable; above 25% suggests bad matchmaking or bad items) |
| **Expiry rate** | `EXPIRED / all` | < 10% |
| **Median decision time** | `completed_at − created_at` | 1.5–5s |
| **D1 / D7 / D30 return** | users with ≥1 pick on day N after first pick | 25% / 12% / 6% |
| **Time to first pick** | **landing → first `COMPLETED`, no account involved** | **< 15s** |
| **Landing → first pick** | share of `/` and `/compare/*` sessions producing ≥1 pick | ≥ 35% |
| **Verification rate** | verified / registered within 24h | ≥ 60% |
| **Guest → registered** | guests who create an account, within 7 days of first pick | ≥ 8% |
| **Guest share of picks** | completed battles by guests / all | monitored, not targeted |
| **Guest vs registered agreement** | share of picks agreeing with the crowd majority, by segment | **within 5pp of each other** — a wider gap means guest picks are behaving differently and [§13.6](#136-guest-play-and-anti-abuse)'s escape hatch is in play |
| **Creators** | share of *registered* users who add ≥1 item | ≥ 10% |
| **Items created / day** | approved only | growth |
| **Battles per item** | mean and P10 (are new items getting seen?) | P10 ≥ 5 within 7 days |
| **Moderation** | REJECTED / REVIEW share; admin queue age | queue age < 24h |
| **Organic sessions** | from Search Console + referrer | growth |
| **Organic → registration** | landing page → account | ≥ 5% |
| **Indexed comparison pages** | Search Console | growth |

### 15.4 Instrumentation requirements

- Every event carries `user_id` (or null), `session_id`, `occurred_at` (server time), and a `source`.
- No PII in event properties. Item text is allowed (it is public); email is not.
- A single `analytics.md` document lists every event name and its properties. Adding an event without adding it there fails review.
- A daily rollup job writes `daily_metrics` (date, metric, value) so dashboards are cheap and history survives raw-event pruning.
- `analytics_events` is pruned after `[CONFIG: 180 days]`; `battles` is never pruned.

---

## 16. Testing strategy

### 16.1 Layers

| Layer | Tool | Runs | What it covers |
|---|---|---|---|
| Unit | `pytest` | every commit | Rating systems, normalisation, slugify, canonicalisation, policy mapping, matchmaking selection given a stubbed pool |
| Property | `hypothesis` | every commit | Invariants over generated inputs (below) |
| Integration | `pytest` + **real Postgres** (testcontainers) | every commit | Repositories, transactions, constraints, migrations |
| API | `pytest` + `httpx.AsyncClient` | every commit | Every endpoint, every error code, auth and CSRF enforcement |
| Concurrency | `pytest` + real Postgres + threads/processes | every commit | The invariants that only break under load |
| Simulation | `pytest` (seeded) + CLI | every commit (short) / nightly (full) | Rating gates §10.5 |
| E2E | Playwright | pre-merge to main | The loop, auth, add-one, rankings, SEO assertions |
| Load | k6 or Locust | before launch, then monthly | Battle loop under concurrency |
| Accessibility | `axe-core` in Playwright | pre-merge | WCAG 2.2 AA on every public template |

**No mocked database, ever, for anything that touches a transaction or a constraint.** The most important correctness properties of this system are enforced by Postgres. A test suite that mocks the database tests nothing that matters here.

### 16.2 Property tests (rating systems)

Run against **every** candidate system, so the suite does not change when the launch system is chosen.

```
∀ Rating a, b over the legal range:
    win_prob(a, b) + win_prob(b, a) == 1                       (within 1e-12)
    a.value > b.value  ⇒  win_prob(a, b) > 0.5                 (equal deviations)
    win_prob(a, a) == 0.5
    0 < win_prob(a, b) < 1                                     (never exactly 0 or 1)
    win_prob is monotonically increasing in a.value
    no NaN, no inf, no OverflowError anywhere in the legal range

    apply(win).rating_after > apply(loss).rating_after          (same inputs — the ONLY
                                                                 ordering property that holds:
                                                                 under EGF, `bonus` can make a
                                                                 loss RAISE a rating, so
                                                                 "a loss lowers the rating" is
                                                                 a WRONG test. Do not write it.)
    apply(a, b, winner=a) mirrors apply(b, a, winner=a)         (order independence)

Glicko only:
    RD never increases on a battle, and never falls below RD_MIN
    g(RD) damping: a certain item beating an uncertain one moves LESS
                   than an uncertain item beating a certain one
EGF only:
    con(r) > 0 and monotonically decreasing;  bonus(r) >= 0 and monotonically decreasing
    R_FLOOR <= rating_after <= C - CEIL_MARGIN
    r >= C or r < R_FLOOR raises RatingDomainError
```

Plus golden-value tests pinning the tables in [§10.2](#102-the-three-candidate-systems) to 4 decimal places, and a worked single-battle Glicko update. If a refactor changes those numbers it must be a deliberate `rating_system_version` bump.

### 16.3 Concurrency tests — the ones that matter most

These are non-negotiable and must run against real Postgres with real connections.

| Test | Assertion |
|---|---|
| `test_concurrent_battle_creation` | 20 parallel `GET /battles/current` for one user → exactly **1** `PENDING` row, all 20 responses carry the **same** `battle_id` |
| `test_double_click_pick` | 2 simultaneous `pick` with the same `winner_id` → 1 `COMPLETED` battle, exactly **2** `rating_events` rows, item rating moved **exactly once**, both responses `200` and identical |
| `test_conflicting_picks` | 2 simultaneous `pick` with *different* `winner_id` → one `200`, one `409`, one rating application |
| `test_pick_and_skip_race` | simultaneous `pick` and `skip` → exactly one terminal state, ratings consistent with it |
| `test_deadlock_free_opposite_pairs` | 50 concurrent battles across overlapping item pairs in randomised order → **zero** deadlocks (this is the ascending-lock-order test) |
| `test_expiry_race` | `pick` submitted at exactly `expires_at` → either `200` with a rating change or `410` with none; never both, never neither |
| `test_sweeper_vs_pick` | sweeper `UPDATE` running concurrently with a `pick` → no lost rating, no double expiry |
| `test_comparison_get_or_create_race` | 20 parallel first-battles on the same pair → exactly **1** `comparisons` row |
| `test_slug_collision_race` | 20 parallel items with the same text → 1 succeeds, 19 get `409 already_exists` |
| `test_counter_consistency` | after 1,000 random concurrent operations: `items.battle_count`/`win_count`/`loss_count` and `comparisons.*` match a recount from `battles`, exactly |
| `test_concurrent_guest_creation` | 20 parallel cookie-less `GET /battles/current` → 20 distinct guests, each with exactly one pending battle; **no guest gets two** |
| `test_guest_conversion_preserves_history` | a guest plays 10 battles, registers, and every battle, rating contribution and session still belongs to the same `user_id` |
| `test_conversion_race` | registration and a pick submitted simultaneously on one guest session → both succeed, exactly one rating application, `is_guest` ends `false` |
| `test_deletion_preserves_ratings` | delete an actor with 50 completed battles → item ratings, `rating_events` and all counters are **byte-identical** before and after; `battles.user_id` is `NULL`; no `users` row remains; no session or token survives |
| `test_deletion_frees_pending_index` | deleting an actor with a `PENDING` battle leaves the partial unique index consistent and does not block a new actor |

### 16.4 API and integration coverage

Every endpoint tested for: happy path, unauthenticated, wrong-owner, malformed body, oversized body, missing CSRF, rate limit exceeded, and every documented error code. Specifically:

- `GET /battles/current` **must not include any rating field** — asserted by schema comparison, not by eyeball. This test is the guard on `[P4]` and must fail loudly if anyone adds a field.
- Repeated `GET /battles/current` within the TTL returns the identical `battle_id`.
- A battle belonging to user A returns `404` (not `403`) for user B.
- An expired battle returns `410` and leaves both item ratings byte-identical.
- Item creation with `NullProvider` is refused when `ENV=production`.
- A cookie-less `GET /api/battles/current` returns a battle **and** a session cookie, and creates exactly one `users` row with `is_guest = true`.
- A guest calling `POST /api/items` gets `401`, not `403` or a validation error — the gate is authentication, and the message names it.
- Rendering `/` server-side creates **zero** `users` rows and **zero** battles.
- The janitor deletes only guests with zero completed battles past the TTL, and never a registered user.

### 16.5 E2E (Playwright)

Register → verify (token pulled from the outbox table) → play 5 battles → skip 1 → check ratings changed → add an item → see it in the next battle → open rankings → open an item page → open a comparison page → log out → log in.

Plus a dedicated **SEO assertion suite** on a seeded database:

- Every public template has exactly one `<h1>`, a `<title>`, a `meta description`, and a self-referencing `<link rel=canonical>`.
- `/compare/b-vs-a` returns `301` to `/compare/a-vs-b`.
- `/compare/x-vs-y` for a pair with no comparison row returns `404`.
- A comparison with 9 battles emits `noindex,follow`; with 10 it emits `index,follow`.
- A hidden item's page returns `410`.
- Item text containing `<script>`, quotes and unicode renders escaped in HTML, in `<title>`, in OG tags and in JSON-LD.
- `robots.txt` in a non-production environment contains `Disallow: /`.
- JSON-LD on every template parses and validates against its schema type.
- With JavaScript disabled, `/item/{slug}` and `/compare/{slug}` still contain the item text and all internal links.

### 16.6 Load testing

Target for launch: **500 concurrent players sustained**, p95 `pick` latency < 200ms, zero deadlocks, zero constraint violations, zero double-applied ratings. Verified by recounting `rating_events` against `battles` after the run. Measure connection pool saturation — the `FOR UPDATE` locks in the pick transaction are the bottleneck to watch.

### 16.7 CI

Every PR: lint (`ruff`, `mypy --strict` on the rating and battle modules, `eslint`, `tsc`), migrations-from-empty + autogenerate-diff-is-empty, unit + property + integration + API + concurrency + short simulation. Pre-merge to main adds E2E, a11y, and the full simulation gates. Coverage floor 85% overall, **100% on `pickone/rating/` and `pickone/battles/`** — those two modules are where a bug is silent and permanent.

---

## 17. Technical architecture

### 17.1 The stack

| Layer | Choice | Why |
|---|---|---|
| **Backend** | **FastAPI** (Python 3.12), SQLAlchemy 2.0 async, Pydantic v2, Alembic, `asyncpg` | The team is Python. FastAPI gives typed request/response models, async I/O for the moderation call, and OpenAPI for free. The domain logic — ratings, transactions, matchmaking — is exactly the kind of code Python is good at and the kind that benefits most from a familiar language. |
| **Database** | **PostgreSQL 16**, managed | Every load-bearing invariant in this system is a Postgres feature: partial unique indexes, `CHECK`s, `FOR UPDATE`, advisory locks, `ON CONFLICT`, `JSONB`, materialised views. There is no second datastore in MVP. |
| **Frontend** | **Next.js 15 (App Router), TypeScript, Tailwind** | SEO is a core requirement, and public pages must be server-rendered with correct metadata, ISR, sitemaps, and per-page OG images. Next's Metadata API and `ImageResponse` do this natively. The game screen is one client component. |
| **Worker** | One Python process: APScheduler for cron-like jobs + a `FOR UPDATE SKIP LOCKED` poller over `outbox_jobs` | The MVP's async work is: expire battles, refresh the rankings view, rebuild sitemaps, send emails, run reconciliation. That is a cron and a queue, both of which Postgres does well enough at this scale. |
| **Email** | Resend or Postmark behind an `EmailProvider` protocol | Two templates. Deliverability matters (verification emails), hosting an SMTP stack does not. |
| **Moderation** | OpenAI `omni-moderation-latest` behind `ModerationProvider` | §12.4 |
| **Hosting** | Two containers (api, worker) + Next.js app + managed Postgres, behind a CDN. Fly.io / Railway / Render, or Hetzner + Docker Compose + Caddy | §17.4 |
| **Observability** | `structlog` JSON logs, Sentry, Prometheus-format `/metrics`, `/healthz` + `/readyz` | §17.5 |

### 17.2 The frontend decision, honestly

The alternative is **FastAPI + Jinja2 + htmx**: one language, one deployment unit, no Node in production, excellent SEO by default (it is all server-rendered HTML), and a smaller surface for a small team. It would genuinely be simpler, and `[P7]` favours simple.

**Next.js wins anyway, for three specific reasons:**

1. Per-page dynamic **Open Graph images** are a real acquisition channel for a product whose output is shareable comparisons, and `ImageResponse` makes them a 40-line file rather than a headless-browser service.
2. The game screen's feel — optimistic press states, a 180ms cross-fade with no layout shift, gesture handling, keyboard, prefetched next pair — is meaningfully better with a component model and client-side state. This screen is the product.
3. ISR with on-demand revalidation gives the right caching semantics for hundreds of thousands of item and comparison pages without a bespoke cache layer.

**The tipping condition, stated up front:** if the team is one Python developer and hiring frontend help is not planned, choose Jinja + htmx, accept static OG images and simpler transitions, and everything else in this specification is unchanged — the API contract, the domain model, the invariants and the SEO rules are all frontend-agnostic. This is a genuine fork, not a hedge; decide it before M0 and record it in `docs/DECISIONS.md`.

### 17.3 Module boundaries (backend)

```
pickone/
├── core/           config, logging, errors, security primitives, clock
├── db/             engine, session, base, migrations/
├── auth/           users, sessions, tokens, password hashing, dependencies
├── items/          creation, normalisation, slugs, repository
├── moderation/     providers/, policy, service
├── rating/         engine.py (PURE), config.py, simulate.py     ← no DB imports, ever
├── matchmaking/    strategies.py, selector.py                   ← no rating imports, ever
├── battles/        service.py (transactions), state.py, repository.py
├── comparisons/    repository, canonicalisation, slugs
├── rankings/       queries, materialised view refresh
├── public/         read-only endpoints for SEO pages
├── admin/          moderation queue
├── analytics/      event ingest, rollup views
├── worker/         scheduler, jobs/, outbox runner
└── api/            routers, dependencies, middleware (auth, csrf, ratelimit, request-id)
```

Enforced boundaries (by import-linter or an equivalent CI check, because these are the boundaries that keep the system understandable):

- `[INVARIANT]` `rating/` imports **nothing** from `db/`, `battles/`, `matchmaking/` or any framework. It is pure functions over floats and a frozen config. This is what makes it simulatable and 100%-testable.
- `[INVARIANT]` `matchmaking/` never imports `rating/`. It reads the `rating` *column*; it never computes one.
- `battles/` is the only module that writes to `items.rating`, `rating_events`, `battles` or `comparisons` counters.
- `public/` is read-only — it holds no write path at all.

### 17.4 Deployment

**Target: a Raspberry Pi behind a Cloudflare Tunnel.** Decided during M0 and recorded here rather than in a generic "pick a PaaS" list, because several choices elsewhere in this document depend on it.

```
                     Cloudflare edge          (TLS, HSTS, caching, Access policies)
                          │
                          │  outbound-only tunnel — the Pi opens NO inbound ports
                    ┌─────▼──────┐
                    │ cloudflared│  systemd unit, /etc/cloudflared/config.yml
                    └─────┬──────┘
       /api/* ────────────┼──────────── /logs ─────────────── everything else
             │            │                  │                        │
     127.0.0.1:8100       │          127.0.0.1:8180          127.0.0.1:3100
             │            │                  │                        │
        ┌────▼────┐  ┌────▼────┐  ┌──────────▼──────────┐        ┌────▼────┐
        │ FastAPI │  │ worker  │  │ dozzle → dockerproxy│        │ Next.js │
        │  N=1    │  │  N=1    │  │  (POST=0, no socket)│        │  N=1    │
        └────┬────┘  └────┬────┘  └─────────────────────┘        └─────────┘
             └────────────┴───────────────┐
                                   ┌──────▼──────┐
                                   │ PostgreSQL  │  unpublished; volume-backed
                                   │     16      │
                                   └─────────────┘
```

- **Same origin for the frontend and `/api`.** The tunnel routes `^/api/` to the API and everything else to Next, on one hostname. This is what allows `SameSite=Lax` cookies and no CORS ([§13.3](#133-csrf)) — and it is why the tunnel's ingress order matters: the frontend rule is a catch-all and must stay last.
- **Nothing is published to the network.** Every container port binds `127.0.0.1`. Postgres and the docker-socket proxy are not published at all. The Pi has no inbound firewall rule to get wrong.
- **The Pi never builds.** `make push` produces multi-arch (`linux/arm64,linux/amd64`) images with buildx and pushes them to a registry; the Pi pulls. A Next.js build on a Pi is slow enough to be a bad idea, and it would put a toolchain on the production host for no reason.
- **Deploys are tag-triggered.** Pushing `v<VERSION>` fires a workflow on a self-hosted `pi-prod` runner: pull, `migrate` to completion, `up -d`, then **verify** — `/readyz`, the web root, and a log assertion that the worker took its singleton lock. A deploy that silently loses the worker is the failure this catches; the worker is the one service with no HTTP surface to probe.
- **Exactly one worker instance.** The scheduled jobs are not designed for concurrent execution; a second would double-run the sweeper harmlessly and double-send email harmfully. Enforced by a session-level advisory lock. A *starting* worker waits `[CONFIG: WORKER_LOCK_WAIT_SECONDS = 30]` for a departing one, because on redeploy the outgoing container's Postgres connection — and therefore its lock — can outlive the container by seconds. Without that wait, every deploy is a restart loop that resolves by luck. The wait is bounded and then it exits: **two workers is worse than none.**
- **Connection pooling:** `asyncpg` pool of 4 per API process. The pick transaction holds row locks; an oversized pool converts contention into lock waits, and a Pi has few cores to spend on either. Add PgBouncer (transaction mode) only when API processes exceed 8 — note that transaction-mode pooling is incompatible with session-level advisory locks, which is exactly why battle creation uses `pg_advisory_xact_lock` (transaction-scoped) while only the worker singleton uses the session-level form.
- **Postgres is tuned for the board, not for a server.** `shared_buffers=256MB`, `work_mem=8MB`, `max_connections=40`, `random_page_cost=1.1` (SSD/SD, not a spindle). `synchronous_commit` stays **on** — a pick is a durable fact and is not worth trading for throughput. `log_lock_waits=on`, because lock contention in the completion transaction ([§9.4](#94-battle-completion--the-atomic-transaction)) is the failure mode most likely to bite here.
- **Log rotation is mandatory, not hygiene.** Every service uses `json-file` with `max-size=10m, max-file=5`. An SD card filled by container logs takes the database down with it.
- **Backups:** the managed-PITR assumption does **not** hold on self-hosted hardware. A nightly `pg_dump` to off-device storage is required, and the restore must be rehearsed with a measured RTO before launch ([M7](milestones/M7-launch.md)). **This is the biggest operational risk the Pi introduces** and it is not optional.
- **Zero-downtime deploys:** migrations stay backward-compatible with the previous release (expand/contract), so `migrate`, `api` and `worker` can roll without a coordinated stop.
- **Environments:** `local` (docker compose, built from source, hot reload), `production` (Pi, prebuilt images). There is no preview environment on this hardware — the `preview` env value and its `Disallow: /` behaviour remain in the config register for when one exists ([§14.8](#148-robotstxt)).
- **`NEXT_PUBLIC_*` is inlined at image build time**, not read from the environment at runtime. `NEXT_PUBLIC_ENV=production` is what makes `robots.txt` allow crawling, so an image built without it ships a site-wide `noindex`. The build args live in `make push`; treat them as part of the release, not as configuration.

**The Pi is shared.** It already runs other projects, so the deployment owns *namespaced* host artefacts and nothing else: `/etc/cloudflared/pickone.yml` (never the shared `config.yml`), a dedicated `cloudflared-pickone.service` (never `cloudflared service install`, which repoints the shared unit), `~/actions-runner-pickone/` with the label `pickone-prod` (never `~/actions-runner/` or `pi-prod`, which would carry another repo's `DEPLOY_DIR` and let either workflow deploy the wrong project), ports 8100/3100/8180, and an image cleanup scoped to `ohiliazov/pickone-*` rather than a host-wide prune. `scripts/pi/00-preflight.sh` verifies all of this **before** writing anything, and **fails closed** — an artefact it cannot positively identify as its own is a reason to stop, not permission to continue. `scripts/pi/test-preflight.sh` exercises those guards in a sandbox on any machine, so the claim is tested rather than asserted.

**What the Pi costs, stated plainly.** One board is a single point of failure with no managed failover, no PITR, and modest IO. That is an acceptable trade for a product whose traffic is unknown and whose write path is a handful of short transactions — but it makes the backup rehearsal and the log rotation above load-bearing rather than best-practice. Scaling out means moving Postgres first, not the API.

### 17.5 Observability

- **Structured logs** (`structlog`, JSON) with a `request_id` propagated from the edge through Next.js into FastAPI and into every log line. Every battle transaction logs `battle_id`, `user_id`, `comparison_id`, outcome, and duration at INFO.
- **Sentry** on both backend and frontend, with `rating_system_version` and `request_id` as tags.
- **Metrics** (`/metrics`, Prometheus format) — the ones that actually get alerted on:
  - `battles_created_total`, `battles_completed_total{status}`, `battle_pick_duration_seconds`
  - `battle_transaction_retries_total`, **`battle_deadlocks_total`** (alert on **any**)
  - `rating_clamp_total{bound}` (alert on any — §10.6)
  - `moderation_provider_latency_seconds`, `moderation_provider_errors_total`, `moderation_circuit_open`
  - `matchmaking_duration_seconds`, `matchmaking_fallback_total`, `matchmaking_exhausted_total`
  - `pending_battles_gauge`, `sweeper_expired_total`
  - `outbox_queue_depth`, `outbox_failed_total`
- **Alerts (page):** deadlocks > 0; rating clamps > 0; `5xx` rate > 1%; moderation circuit open > 5 min; sweeper not run in 5 min; outbox depth > 500; DB connection saturation > 80%.
- **Nightly reconciliation job** (this is the one that catches silent corruption): recount `items.battle_count/win_count/loss_count` and `comparisons.*` from `battles`; assert `rating_events` has exactly two rows per `COMPLETED` battle; assert no `COMPLETED` battle has a `winner_id` outside its comparison; assert no user has two `PENDING` battles. Any mismatch pages, and the job reports rather than repairs — silent auto-repair would hide the bug that caused it.

### 17.6 What is deliberately absent

Redis, Celery, Kafka, Elasticsearch, a separate analytics warehouse, a GraphQL layer, a service mesh, Kubernetes, feature-flag infrastructure, a CDN-edge compute layer, a read replica. Each has a named trigger condition in this document or is simply not needed at MVP scale. `[P7]`

---

## 18. MVP implementation plan

Eight milestones. Each is a separate handoff with its own brief in [`milestones/`](milestones/). The critical-path ordering matters in two places: **the rating engine is validated before anything depends on it (M3 before M4)**, and **the battle loop is correct before it is made pretty (M4 before M5)**.

```
M0 Foundations
   └─► M1 Auth ──┬─► M2 Items & moderation ──┐
                 │                            ├─► M4 Battles ──► M5 Game UI ──┐
                 └────────────────────────────┤                               ├─► M7 Launch
        M3 Rating systems (parallel, no deps) ─┘                M6 SEO pages ──┘
```

| # | Milestone | Depends on | Can run parallel with | Rough size |
|---|---|---|---|---|
| **M0** | Foundations & scaffolding | — | — | S |
| **M1** | Authentication & accounts | M0 | M3 | M |
| **M2** | Items & moderation | M1 | M3 | M |
| **M3** | Rating systems & simulation | M0 | M1, M2 | M |
| **M4** | Comparisons, matchmaking & battle lifecycle | M2, M3 | — | **L — the hard one** |
| **M5** | The game UI | M4 | M6 | M |
| **M6** | Public SEO surfaces | M2, M4 | M5 | L |
| **M7** | Analytics, hardening, seed data & launch | M5, M6 | — | M |

**M3 is deliberately off the critical path's front** — it has no database dependency at all (pure functions plus a simulator), so it can be built and its gates run while M1/M2 are in flight. This matters more now than it did: choosing between **three rating systems** ([§10.6](#106-simulation--the-decision-procedure)) is the longest-lead-time decision in the project, and it must not be made under launch pressure. M2 ships `items.rating_deviation` before M3 finishes, precisely so the choice stays open.

**M4 is the milestone to over-invest in.** Every invariant in §9 lives there, its bugs are silent and permanent, and no amount of later polish repairs a corrupted rating history.

Full briefs: [M0](milestones/M0-foundations.md) · [M1](milestones/M1-auth.md) · [M2](milestones/M2-items-moderation.md) · [M3](milestones/M3-rating-engine.md) · [M4](milestones/M4-battles.md) · [M5](milestones/M5-game-ui.md) · [M6](milestones/M6-seo.md) · [M7](milestones/M7-launch.md)

---

## 19. Future roadmap

Design for these; build none of them. Each phase gets its own spec when its time comes.

### Phase 2 — Demographic rankings

**Goal:** `Carbonara — Worldwide #18 · Poland #4 · Age 30–39 #7`.

Shape of the work:

- Optional, explicitly consented profile attributes on `users`: `country`, `birth_year` (→ age band), `gender`. Consent is a separate, revocable, timestamped record (`user_consents`), not a checkbox buried in registration.
- `[INVARIANT]` **Users who do not consent must remain fully functional** — they play, they create, their picks count toward the worldwide ranking exactly as before. Their picks simply do not enter demographic aggregates.
- A separate aggregate table (`item_ratings_by_segment`) rather than more columns on `items`. Ratings per segment are computed by **replaying `rating_events` filtered by segment** — which is possible only because §6 made that table complete and append-only. This is the concrete payoff of the audit design.
- **Privacy floors:** a segment ranking is only shown when the segment has at least `[CONFIG: MIN_SEGMENT_USERS = 500]` distinct contributing users *and* the item has at least `[CONFIG: MIN_SEGMENT_BATTLES = 50]` battles in that segment. Below the floor, the segment is not displayed and not exposed by the API — otherwise "age 65+, Liechtenstein" identifies one person.
- New SEO surface: `/rankings/{country}` and `/rankings/{age-band}`, subject to the same indexing thresholds as everything else. This roughly multiplies the indexable page count, so the thresholds need re-tuning at that time.
- Battles do **not** need a denormalised segment column: the segment is derivable from `battles.user_id`. Do not denormalise until a query proves it necessary.

### Phase 3 — Similar-item detection and merging

**Goal:** `Carbonara` / `Spaghetti Carbonara` / `Spaghetti alla Carbonara` become one item without losing history.

Shape of the work:

- Candidate generation: normalisation and trigram similarity (`pg_trgm`) for cheap recall, then embedding cosine similarity for precision. Both offline, in the worker.
- A `merge_candidates` table with a confidence score, reviewed by **the community using the PickOne mechanism itself** — "Are these the same thing?" is a pairwise-ish question the product is already shaped for — plus human moderation for anything above a confidence threshold.
- Merging is an **explicit, reversible, audited operation**: `item_merges (from_item_id, to_item_id, merged_at, merged_by, reversal_of)`. The losing item is not deleted; it is marked `MERGED` with a pointer.
- History is preserved by construction: `battles` and `rating_events` continue to reference the original item ids. The survivor's rating is recomputed by replaying both items' events (again, only possible because of §6).
- Comparisons that become self-comparisons after a merge (`A vs A`) are retired, not deleted.
- SEO: the merged item's slug `301`s to the survivor via the `item_slug_aliases` table anticipated in §14.9. Comparison slugs containing the merged slug also `301`. This is the first milestone that needs redirect infrastructure.

### Phase 4 — Translations and localisation

**Goal:** PickOne in other languages, with wording chosen by native speakers.

`AI translation is the starting point, not the final authority.`

Shape of the work:

- `item_translations (item_id, locale, text, source, status, votes)`, with `source ∈ {AI, USER}`.
- AI produces the initial candidate per locale. Users who speak the language then **pick between two candidate wordings using the same battle mechanism** — this is the moment the pairwise engine stops being about items. It is why §6.3 keeps the rating engine and battle lifecycle written against abstract subject pairs.
- A `translation_battles` flow reuses the rating engine with its own config profile and its own matchmaking rules; the schema will need `battles` to become polymorphic over subject type (or a parallel table — decide then, with real requirements).
- Multilingual SEO: locale-prefixed routes (`/es/item/...`), `hreflang` clusters with `x-default`, per-locale sitemaps, per-locale canonicals. Do not launch a locale until its item coverage exceeds a threshold, or it becomes thin content in a new language.
- Item display casing (§5.1) must become locale-aware at this point.

### Phase 5 — Non-intrusive advertising

**Goal:** revenue that does not touch the loop.

`[INVARIANT]` **No ad may appear on `/play`, and no ad may sit between PICK and NEXT.** `[P2]` This is not a starting position for negotiation.

Permitted surfaces: `/rankings` (between pagination blocks), `/item/{slug}` (below the fold), `/compare/{slug}` (below the fold), and future discovery pages. Requirements: no layout shift (reserved slots with fixed dimensions), no interstitials, no autoplay, lazy-loaded below the fold, and a hard CLS/INP budget that ad code must meet or be removed. The privacy policy and CSP both change materially here (§13.7) — that is part of the Phase 5 scope, not an afterthought.

### Beyond — pairwise consensus as a platform

The same mechanism can decide translation wording, synonym preference, merge confirmations, and moderation edge cases. **Do not build for this now.** The only obligation MVP carries is the one already discharged in §6.3 and §17.3: the rating engine and battle lifecycle are written against abstract subject pairs and do not know what an Item is.

---

## 20. What to avoid

### 20.1 Product anti-patterns

| Avoid | Why |
|---|---|
| **Becoming a review site** | The moment "why did you pick this?" appears, PickOne is Yelp with extra steps. There are no reviews, no stars, no justifications. |
| **Categories** | "Compare food to food" is the single most requested feature and the one that would kill the product. Carbonara vs Fitting bed sheets **is** the product. `[P6]` |
| **A "neither" or "both" option** | Skip already covers "I don't want to choose". A third outcome adds a draw to the rating model, which was explicitly removed, and gives users a way to avoid deciding — which is the one thing the product asks of them. |
| **Explaining the rating** | The user never needs to know what a K-factor is. `[P3]` |
| **Gamification layers** | Streaks, XP, levels, badges, daily goals. The loop is already the reward. Each layer adds a second primary verb. `[P1]` |
| **Social features** | Comments on items, following users, profiles as identity. The Comparison entity is designed to hold future comments — that is Phase-something and it is community data on a *pair*, never a social graph. |
| **Showing ratings before the pick** | Poisons the dataset permanently and irreversibly. `[P4]` |
| **Personalised matchmaking** | "Show me things I'll enjoy comparing" produces a per-user filter bubble and a ranking that means nothing globally. |
| **A "trending" or "controversial" feed** | A second primary surface competing with the loop. Later, maybe, as SEO pages — never as a competing home screen. |
| **Making the matchups fair** | A perfectly-tuned matchmaker produces the most information per battle and the least fun per battle. `[P6]` |
| **Asking for demographics at registration** | Phase 2 needs consent, and consent asked at the wrong moment costs registrations. Ask later, in context, optionally. |

### 20.2 UX anti-patterns

| Avoid | Why |
|---|---|
| **Anything between PICK and NEXT** | Modals, interstitials, "share this result", ads, confirmations. `[P2]` |
| **A results page after each pick** | The reveal is 900ms in place. Navigation breaks the loop. |
| **Error modals for expiry** | `410` is a normal, expected, frequent event. It gets one quiet line, not a dialog. |
| **Spinners on the card swap** | A spinner in the loop makes the product feel slow at exactly the moment it must feel instant. Skeleton the loser card if the response is late; never block. |
| **Layout shift when the pair changes** | Card geometry is fixed; only content cross-fades. CLS 0. |
| **Swipe as the only way to do anything** | Gestures are undiscoverable and inaccessible. Every gesture has a button. `[§5.7]` |
| **Corporate copy** | "Submit your vote", "Rate this item", "Thank you for your feedback". `[§5.6]` |
| **A tutorial, onboarding carousel, or tooltip tour** | The product is two cards and one instruction. If it needs a tutorial, the design failed. |
| **Cookie consent theatre** | MVP sets one strictly-necessary session cookie and needs no banner. Do not add third-party trackers that would require one. |
| **Infinite scroll on rankings** | Breaks crawlability, breaks deep-linking, breaks the back button. Paginate. |

### 20.3 Engineering anti-patterns

| Avoid | Why |
|---|---|
| **Enforcing the one-pending-battle rule in application code only** | Race conditions are guaranteed with multiple workers. The partial unique index is the mechanism; the application check is an optimisation. `[§9.3]` |
| **Locking items in a non-deterministic order** | Guaranteed deadlocks under load. Always ascending id. `[§9.4]` |
| **`SERIALIZABLE` isolation as a substitute for explicit locks** | Adds retries and hides the real concurrency design. Explicit `FOR UPDATE`, `READ COMMITTED`. |
| **Letting the client send anything but `winner_id`** | Ratings, item ids to compare, timestamps, "expected" outcomes — all attack surface. The battle id and one winner id is the entire input. `[P5]` |
| **Mocking the database in tests** | Every invariant that matters is a Postgres constraint. Mocks test the mock. `[§16.1]` |
| **Recomputing ratings synchronously for display** | `items.rating` is a column. Read it. |
| **Putting the rating formula inline in the battle service** | It must be pure, isolated and simulatable, or the parameters can never be validated. `[§17.3]` |
| **Generating a comparison page for every possible pair** | 10k items → 50M URLs → a thin-content penalty. Only real comparisons are addressable. `[§14.3]` |
| **Canonicalising paginated pages to page 1** | Removes pages 2+ from the index entirely. Self-canonical. `[§14.9]` |
| **`AggregateRating`/`Review` structured data** | Misrepresents the content and risks a manual action. `[§14.6]` |
| **`lastmod = now()` in the sitemap** | Destroys crawl efficiency and trains the crawler to ignore the signal. |
| **Adding Redis/Celery/Kafka "because we'll need it"** | Each has a named trigger condition. Wait for it. `[P7]` |
| **Retroactively recomputing ratings after a config change** | MVP does not do this. If it ever does, it is a deliberate, versioned, audited migration — never a silent recompute. |
| **Auto-repairing reconciliation mismatches** | Hides the bug that caused them. Report and page. `[§17.5]` |
| **Trusting `decision_ms` or any client timing** | Recorded for analytics, never used in a rule. |
| **A separate `guest_sessions` table** | Doubles every constraint, query and test to model something that is already a `User`. [§6.1](#61-entities) |
| **Anonymising a deleted user in place** | A surviving row with a stable id still links every action to one identity. Delete it; NULL the battles. [§13.7](#137-account-deletion-and-the-audit-trail) |
| **Deleting a departed user's battles** | Retroactively rewrites a public artefact that everyone else's picks were measured against. |
| **Bot fingerprinting to stop crawler-created guests** | Costs you Googlebot and real users to save kilobytes. [§14.2](#142-rendering-strategy) |
| **Storing a rating as a bare float** | Blocks the certainty model and forces a migration on the largest table. Always `(value, deviation)`. |
| **`if item.rating:`** | `0` is a legal, meaningful rating and is falsy. Use `is None`. [§10.4](#104-zero-is-the-origin-and-the-sign-is-the-product) |
| **Rendering a rating without its sign** | `487` hides the one thing the number is for. Always `+487` / `−312`. |
| **Colouring positive green and negative red as the only signal** | Colour-only encoding, and it moralises a joke. The glyph carries the sign. |
| **Clamping, flooring, or shifting ratings to avoid negatives** | Breaks conservation and destroys the meaning of the sign. |
| **Reaching for Glicko-2** | Its volatility term models changing competitor strength. Items do not change. [§10.3](#103-what-glicko-2-would-add-and-why-it-is-the-overengineered-choice) |
| **Detailed moderation rejection reasons** | A free oracle for probing the classifier. `[§12.5]` |
| **Adding a field to `GET /battles/current`** | The no-ratings-before-the-pick rule is enforced by a schema test. If that test fails, the product principle is being violated, not the test. `[P4]` |

---

## 21. Implementation handoff

### 21.1 How to hand off a milestone

Give the implementation agent exactly three things:

1. **This document** (`SPEC.md`) as reference.
2. **One milestone brief** from [`milestones/`](milestones/) as the task.
3. **The invariant card** below, verbatim, in the prompt.

Then this instruction:

> Implement milestone `<Mn>` exactly as specified in `docs/milestones/<Mn>-*.md`. Read `docs/SPEC.md` sections referenced by the brief before writing code. Do not implement anything listed under **Non-goals**. Do not add fields, endpoints, tables or configuration that the brief does not name. If the brief is ambiguous or appears to conflict with `SPEC.md`, stop and ask rather than choosing. Every item under **Acceptance criteria** must be demonstrably true, with the test that proves it, before you report completion.

One milestone per agent, one at a time. M1/M2 and M3 may run concurrently in separate worktrees since they share no files; nothing else should overlap.

### 21.2 The invariant card

> Paste this into every implementation prompt. These are the rules a milestone may never break, regardless of what it is building.
>
> 1. **Every actor has exactly one standing pending battle** (unless their catalogue is exhausted), enforced by the partial unique index `one_pending_battle_per_user`. Application checks are an optimisation, never the mechanism.
> 2. **`PENDING` is the only non-terminal battle state.** `COMPLETED`, `SKIPPED` and `EXPIRED` are final forever.
> 3. **Ratings change only on `PENDING → COMPLETED`**, exactly once per battle, guaranteed by `rating_events_battle_item_uq`.
> 4. **Items are locked in ascending id order** in every transaction that locks more than one.
> 5. **`comparisons.item_a_id < item_b_id`** always, with `UNIQUE (item_a_id, item_b_id)`.
> 6. **`GET /api/battles/current` returns no rating, rank, deviation, or count of any kind.** No exceptions, ever.
> 7. **`pickone/rating/` imports nothing from `db/` or any framework.** Pure functions and a frozen config.
> 8. **`matchmaking/` never imports `rating/`.**
> 9. **The client sends only `battle_id` + `winner_id`.** Everything else about a battle is derived server-side from the session.
> 9a. **A guest is an ordinary `User` row with `is_guest = true`.** No code path may branch on guest-ness except the three documented gates: adding an item, reporting an item, deleting an account.
> 9b. **Deleting an actor deletes the `users` row and NULLs `battles.user_id`.** Ratings, `rating_events` and every counter are untouched. Never anonymise in place; never delete a battle.
> 9c. **`Rating` is always `(value, deviation)`**, whichever system is active. Never a bare float.
> 9d. **Never clamp a rating.** Items start at **0** and negative ratings are a designed feature: the sign means below-average. `[§10.4]`
> 9e. **Never test a rating for truthiness.** `0` is legal and meaningful. Use `is None`.
> 10. **Wrong-owner access returns `404`, not `403`.**
> 11. **No public page requires JavaScript to render its content or its internal links.**
> 12. **Only comparisons that exist in the database are addressable.** No route materialises a page for an unplayed pair.
> 13. **`rating_events` is append-only.** No `UPDATE`, no `DELETE`, ever.
> 14. **No test that touches a transaction or a constraint may mock the database.**
> 15. **Nothing goes between PICK and NEXT.**

### 21.3 The configuration register

Every `[CONFIG]` value in this document must exist as a single named setting in `pickone/core/config.py` (backend) or `lib/config.ts` (frontend), with the default given here, loaded from the environment, and validated at boot. A magic number in a function body is a review failure. M0 creates the register; each subsequent milestone adds only its own keys.

### 21.4 Definition of done, for every milestone

- Every acceptance criterion has a named test that proves it, and that test is in CI.
- Migrations run from empty and the autogenerate diff is empty.
- `ruff`, `mypy` (strict on `rating/` and `battles/`), `eslint`, `tsc` all clean.
- New `[CONFIG]` keys are in the register with defaults and documented.
- New analytics events are in `analytics.md`.
- Nothing from **Non-goals** was built.
- The invariant card still holds — and where the milestone touches an invariant, there is a test asserting it.
