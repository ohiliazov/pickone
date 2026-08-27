# Seed catalogue

`items.txt` — one item per line, curated by the product owner ([DECISIONS.md Q9](../docs/DECISIONS.md)).
M7 builds the loader; this directory is only the content.

**100 items.** Validated against [SPEC §12.2/§12.3](../docs/SPEC.md#123-structural-validation):

| check | result |
|---|---|
| Hard failures (length, charset, URLs, control chars, digits) | **0** |
| Duplicates after `normalized_text` | **0** |
| Slug collisions | **0** |
| Slugs containing the reserved `-vs-` token | **0** |
| Length | 27–45 chars, median 39 — all under the 64 limit *and* the 48 nudge |

## Shape of the catalogue

Every item is a small everyday experience, phrased as a gerund or noun phrase.
Two consequences the loader and the rating simulation should know about:

**By §11.4's letter this is one domain, not eight.** The rule exists to stop
matchups being *sensible*, and the axis this catalogue actually shares is
**valence**, not subject:

| | count | share |
|---|---:|---:|
| pleasant | 28 | 28% |
| unpleasant | 47 | 47% |
| neutral / ambiguous | 25 | 25% |

Of the 4,950 possible pairs: 26% are clear-pleasant against clear-unpleasant
(a near-trivial pick), 29% are same-valence and genuinely contested, 43%
involve a neutral item. So roughly three-quarters of matchups carry real
tension — the diversity that matters is present, just along a different axis
than §11.4 anticipated.

**The ranking this produces is hedonic**, not general. It ranks small pleasures
and annoyances rather than "everything", which is narrower than the brand's own
examples (Carbonara, Ferrari 911, Monday) but sharper as a first catalogue.

## Sizing

100 items → 4,950 distinct pairs → about 412 sessions at 12 picks before an
actor repeats a pair. Above §11.4's floor of 50, below the preferred 150–300,
so **the default cooldowns are safe** — no need to scale
`USER_PAIR_COOLDOWN_DAYS` or `USER_RECENT_ITEMS` down.
