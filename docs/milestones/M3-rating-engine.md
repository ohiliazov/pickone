# M3 — Rating systems & simulation

**Size:** M · **Depends on:** M0 only · **Parallel with:** M1, M2
**Spec reference:** [§10](../SPEC.md#10-rating-system) in full, [§16.2](../SPEC.md#162-property-tests-rating-systems), [§17.3](../SPEC.md#173-module-boundaries-backend)

## Goal

Three well-established rating systems behind one protocol, and a simulator that proves — with numbers, in CI — which one PickOne should launch with.

**This milestone produces a decision, not just code.** Its real output is `docs/RATING-SYSTEM.md`: the chosen system, its parameters, the full comparison across three candidates and eight scenarios, and the reasoning.

## Scope

- `pickone/rating/types.py`: `Rating = (value: float, deviation: float)` and `Outcome`. **`Rating` is never a bare float**, whichever system is active — this is what makes the systems swappable without a migration on `items`.
- `pickone/rating/system.py`: the `RatingSystem` protocol — `version`, `initial()`, `win_prob(a, b)`, `apply(a, b, winner) -> Outcome`. `Outcome` carries both new `Rating`s **and** the full audit payload for `rating_events`, including the system-specific `terms` dict.
- Three implementations, all pure — no I/O, no ORM, no framework imports:
  - **`Glicko1System`** ([§10.2](../SPEC.md#102-the-three-candidate-systems)) — `g(RD)`, `E`, `d²`, the rating and RD updates, `RD_MIN` floor, `C_INFLATE = 0`. Applied **incrementally** (one battle = one period); the caveat and its justification are in the spec and belong in the module docstring.
  - **`EloSystem`** — logistic `E` on the 400-scale, `K(n)` battle-count schedule (64/32/16 at n<15, n<50, else). Reports a constant deviation.
  - **`EgfSystem`** — the original adaptation. **`win_prob` must use the closed form** `1 / (1 + ((C−r₁)/(C−r₂))^B)` — no `exp`, no overflow. Clamps to `[R_FLOOR, C − CEIL_MARGIN]` with a `rating_clamp_total{bound}` counter; the clamp is a numerical safety net specific to this system, not a product feature.
- `pickone/rating/config.py`: per-system frozen config dataclasses, named profiles, and loading from the environment. **`INITIAL_RATING = 0.0` for all three** — the origin is meaningful ([§10.4](../SPEC.md#104-zero-is-the-origin-and-the-sign-is-the-product)). Elo and Glicko are translation-invariant so this is free; `EgfSystem` is not, and choosing it means re-anchoring `C`, `R_BONUS` and `R_FLOOR` (its `R_FLOOR` must sit well below zero or it clamps every item at its starting value).
- `pickone/rating/simulate.py` + a `pickone-simulate` CLI: the harness and the **eight** scenarios from [§10.6](../SPEC.md#106-simulation--the-decision-procedure). It calls the **real** systems and the **real** matchmaker interface. Define the `PairSelector` protocol here with an in-memory implementation; M4 implements the SQL one against the same protocol.
- Report output: JSON, a markdown comparison table, and plots of the inflation curve, the rating distribution and the **calibration curve**.
- Gate checks `GATE-R1`…`GATE-R9` as assertions the CLI runs and CI calls. **`GATE-R9` (sign agreement) must be reported as a percentage, at several matchmaking mixes, not just pass/fail** — its value decides the product's copy, and the relationship between mix and agreement is not predictable ([§10.6](../SPEC.md#106-simulation--the-decision-procedure)).

## Database changes

**None.** This milestone must not touch the database. If it needs a table, the design is wrong.

## API changes / Frontend changes

None, and none.

## Tests

- **Golden values:** the `con(r)` / `bonus(r)` / `win_prob` table in [§10.2](../SPEC.md#102-the-three-candidate-systems) pinned to 4 decimal places for `EgfSystem`. Equivalent pinned tables for Glicko (`g(350) = 0.6634…`, a worked single-battle update) and Elo.
- **Property tests** (`hypothesis`), per system, over the whole legal range:
  - `win_prob(a,b) + win_prob(b,a) == 1` (within 1e-12)
  - `0 < win_prob < 1` **strictly**, at extreme gaps
  - `win_prob(r,r) == 0.5`; monotonic in the first rating
  - `apply(...win).rating_after > apply(...loss).rating_after` — **the only ordering property that holds.** Under EGF `bonus` can make a loss *raise* a rating; a test asserting "a loss always lowers the rating" is wrong and must not be written.
  - order independence: `apply(a, b, winner=a)` mirrors `apply(b, a, winner=a)`
  - Glicko: `RD` is non-increasing on a battle, and never drops below `RD_MIN`
  - Glicko: `g(RD)` damping means a certain item beating an uncertain one moves less than the reverse
- **Numerical safety:** no `NaN`, no `inf`, no `OverflowError` anywhere in the legal range, for any system. EGF additionally raises `RatingDomainError` on `r ≥ C`, `r < R_FLOOR`, `NaN` or `inf` input.
- **Determinism:** the same seed produces byte-identical simulation output across runs and platforms.
- **Simulation gates:** a short seeded run (10k battles) on every commit; all eight scenarios × three systems nightly and on any change to `rating/`.
- **Boundary import test:** `pickone/rating/` imports nothing from `db`, `sqlalchemy`, `fastapi`, `battles` or `matchmaking`.

## Acceptance criteria

1. `pickone-simulate --system all --scenario all` runs to completion and emits the comparison report.
2. All three systems are evaluated against all eight scenarios, with results committed to `docs/RATING-SYSTEM.md`.
3. **At least one system passes all eight gates**, and it is named as the launch system. If none passes, continue the parameter search **within these three systems** — do not invent a fourth.
4. `GATE-R7` (calibration) is reported as a per-decile table for every candidate, not just pass/fail. It is the gate that says whether a system is *right* rather than merely stable.
4a. `GATE-R9` (sign agreement) is reported as a percentage at a minimum of three matchmaking mixes, and `docs/RATING-SYSTEM.md` states which of the two copy variants — *"people pick it more often than not"* or *"above average"* — the number licenses.
5. `GATE-R2`: no `NaN`/`inf`/domain error anywhere; for `EgfSystem`, the clamp fires **zero** times.
6. `rating/` has 100% line and branch coverage.
7. The import-boundary test passes.
8. `docs/RATING-SYSTEM.md` explains, in prose, what the winning system's parameters mean and what would make you want to change them — including the **negative-ratings** consequence ([§10.4](../SPEC.md#104-zero-is-the-origin-and-the-sign-is-the-product)) and the recommendation to accept it rather than clamp.

## Non-goals

Any database write, any HTTP endpoint, any UI. **Glicko-2 volatility** ([§10.3](../SPEC.md#103-what-glicko-2-would-add-and-why-it-is-the-overengineered-choice) — it models changing competitor strength, and items do not change). TrueSkill, Bayesian alternatives, or any fourth system. Retroactive recomputation. Per-voter weighting. Draws, handicap, colour. Rating decay, seasons, resets. Per-category rating pools. **Any rating floor, clamp or offset.** Items start at 0 and negative ratings are the point: the sign means below-average ([§10.4](../SPEC.md#104-zero-is-the-origin-and-the-sign-is-the-product)).
