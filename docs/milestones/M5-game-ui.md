# M5 — The game UI

**Size:** M · **Depends on:** M4 · **Parallel with:** M6
**Spec reference:** [§4.2–4.5](../SPEC.md#42-first-battle), [§5](../SPEC.md#5-ui--ux-specification) in full

## Goal

The screen that is the product. Two large cards, one tap, instant feedback, next pair — under 1.1 seconds, on a phone, with a keyboard, or with a screen reader.

## Scope

- `/play`: the loop from [§4.3](../SPEC.md#43-the-repeated-loop). One request per pick; the `next` battle from the response drives the swap.
- Cards: vertically stacked at every breakpoint, `clamp()`-based sizing, uppercase display transform as a **theme token** (not baked into the string), `text-wrap: balance`, 3-line clamp with a font-size step-down.
- The animation choreography and its exact timings from [§5.3](../SPEC.md#53-animation-principles), including the optimistic `pointerdown` press state, fixed card geometry across the swap (**CLS 0**), and the skeleton-at-400ms rule instead of a spinner.
- The reveal: winner accent, rating deltas, and the crowd line — `"61% agree"`, shown only when `comparison.battle_count ≥ 20`.
- Skip: button, `Space`, and the downward gesture. Identical latency and prominence to picking.
- Keyboard: the full map in [§5.4](../SPEC.md#54-keyboard), including the focus-dependent `Space` behaviour.
- Gestures: swipe as an **augmentation only**; every gesture has a visible button. Correct handling of scroll conflicts and safe-area insets.
- Error recovery: `410` → silent refetch + one quiet 1.5s line, *"That one timed out."* `409` → silent refetch, no message. Network failure → retry once, then a quiet retry affordance. **No modal, ever.**
- The client-side expiry timer using `expires_at` and `server_time` (never the device clock), silently refetching on expiry when the tab is visible.
- Multi-tab behaviour per [§9.5](../SPEC.md#95-client-side-rules): refetch on `visibilitychange`, re-render if `battle_id` changed, no cross-tab coordination.
- First-run hint (one line, dismissed forever on first pick) and the keyboard-shortcut hint.
- **The guest experience is the default experience.** `/play` works with no session, no interstitial and no "continue as guest" button — the first `GET` establishes the actor invisibly. After `GUEST_PROMPT_AFTER_PICKS = 25` picks, one dismissible line appears above the cards — *"Keep your picks. Make an account."* — which never blocks the loop and never becomes a modal. `[P2]`
- The reveal shows rating deltas only, always signed; **`rating_deviation` is never rendered anywhere.** A delta of `0` is possible and must render as `0`, not as blank. An unranked item's status appears on its own page, not in the loop.
- Accessibility: [§5.7](../SPEC.md#57-accessibility-wcag-22-aa--a-launch-requirement-not-a-follow-up) in full — real `<button>`s, `role="group"`, the `aria-live` result announcement, the "Slower pace" preference honoured with `A11Y_ANNOUNCE_MS`, focus management across the swap (focus must not be lost when the pair changes), reduced-motion fallbacks.
- `/play` is `noindex,nofollow`, `no-store`, and has no footer.

## Database changes

None.

## API changes

None. If this milestone needs an API change, something in M4 was wrong — go fix it there rather than adding a field here.

## Frontend changes

Everything above, replacing the deliberately-ugly M4 `/play`. Plus the `/add` → `/play?seed=` handoff from M2 wired to the real loop, and the polished `Added.` → straight-into-a-battle moment.

## Tests

**Playwright (the loop):**
- Pick 10 battles in sequence; each swap completes and the next pair is interactive within 1.1s.
- The chosen card is visually distinguished before the response arrives (optimistic press).
- Skip 5 battles; ratings unchanged (verified via the API).
- A double click on one card issues exactly **one** `pick` request (button disabled from `pointerdown`).
- With the API forced to `410`, the client recovers silently and shows the timeout line once.
- Two tabs: picking in tab A, then focusing tab B, leaves tab B showing a valid current battle with no duplicate requests.
- Offline mid-pick → retry affordance, no data loss, no duplicate application.

**Visual/layout:**
- CLS is 0 across a pick→swap cycle (measured, not eyeballed).
- Item text of 2, 20 and 60 characters all render inside the card without overflow at 320px, 768px and 1440px widths.
- Both themes render correctly.

**Accessibility (`axe-core` + manual assertions):**
- Zero `axe` violations on `/play` in both themes.
- Full keyboard operation: every action reachable and performable without a pointer.
- The result is announced in the live region with the expected text.
- Focus is never lost or trapped across the swap.
- `prefers-reduced-motion` removes all transforms; the loop still works.
- Every gesture has a working button equivalent.

**Copy:**
- A test asserting the rendered strings on `/play` match [§5.6](../SPEC.md#56-copy-and-terminology) exactly, and that none of the banned words appears anywhere in the route's rendered output.

**Performance:**
- Lighthouse on `/play`: performance ≥ 90 on a simulated mid-tier phone; INP < 200ms.

## Acceptance criteria

1. Tap → next pair interactive in ≤ 1.1s on a throttled mid-tier mobile profile.
2. CLS 0 across the swap.
3. `axe` reports zero violations in both themes.
4. The entire loop is operable by keyboard alone and by screen reader alone.
5. A double click produces exactly one request and one rating application.
6. Expiry and conflict are invisible or near-invisible to the user — no modal, no red error, no navigation.
7. No rating, rank, deviation or count is visible anywhere on screen **before** a pick — asserted by a DOM test on the pre-pick state.
9. A visitor with cleared cookies can load `/play` and pick, with no sign-up prompt before pick 25 and no modal ever.
8. The banned-words test passes.

## Non-goals

Battle history, undo, rematch, sharing a result, streaks, counters, "battles today", sound, haptics beyond one light impact, tutorials or onboarding carousels, animations not listed in [§5.3](../SPEC.md#53-animation-principles), a second interactive surface of any kind. **Nothing new between PICK and NEXT.**
