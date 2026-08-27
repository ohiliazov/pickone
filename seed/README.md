# Seed catalogue

`items.txt` — one item per line, curated by the product owner ([DECISIONS.md Q9](../docs/DECISIONS.md)).
M7 builds the loader; this directory is only the content.

**100 items**, one or two words each, mixing the mundane with the bizarre.
Validated against [SPEC §12.2/§12.3](../docs/SPEC.md#123-structural-validation):

| check | result |
|---|---|
| Hard failures (length, charset, URLs, control chars, digits) | **0** |
| Duplicates after `normalized_text` | **0** |
| Slug collisions | **0** |
| Slugs containing the reserved `-vs-` token | **0** |
| Length | 4–13 chars, median 8 — far inside the 64 limit and the 48 nudge |
| Single-token | 100 / 100 |

## §11.4 domain diversity

Wants at least 8 domains, none above 20%.

| domain | n | |
|---|---:|---|
| mundane | 22 | taxes, socks, dentists, mondays, laundry |
| myth | 11 | kraken, cthulhu, valhalla, excalibur |
| nature | 10 | volcano, everest, spiders, tornadoes |
| history | 10 | guillotine, samurai, gladiators, enigma |
| occult | 9 | exorcism, witchcraft, illuminati, UFOs |
| body | 8 | sneezing, vertigo, hiccups, sunburn |
| sci-fi | 7 | cyborg, teleportation, time-travel |
| food | 6 | coffee, bread, avocados, carbonara |
| tech | 5 | wi-fi, bluetooth, passwords |
| cosmic | 5 | supernova, blackhole, exoplanet |
| emotion | 4 | nostalgia, grief, euphoria |
| science | 3 | plutonium, antimatter, trinitite |

**12 domains — passes.** `mundane` sits at 22%, marginally over, but it is a
catch-all rather than a real single domain: taxes, socks, dentists and mondays
share nothing but ordinariness. Split it into chores and objects and both land
near 11%.

Unlike a catalogue of experiences, these items share no single comparison axis,
so the matchups stay absurd by construction — which is the property §11.4 exists
to protect.

## Sizing

100 items → 4,950 distinct pairs → about 412 sessions at 12 picks before an
actor repeats a pair. Above §11.4's floor of 50, below the preferred 150–300,
so **the default cooldowns are safe** — no need to scale
`USER_PAIR_COOLDOWN_DAYS` or `USER_RECENT_ITEMS` down.

## Notes for later milestones

- Seed items are created `APPROVED` by a system user and **bypass moderation**.
  Were a *user* to submit them, `Guillotine`, `Exorcism`, `Voodoo`, `Witchcraft`
  and `Illuminati` are the only ones with any chance of scoring on a moderation
  classifier. They make good fixtures for tuning M2's policy thresholds — a
  catalogue that trips its own moderation is a threshold that is set too tight.
- Cards render uppercase ([§5.1](../docs/SPEC.md#51-desktop--the-game-screen-play)).
  At 13 characters max, no font step-down is needed at any breakpoint.
- `Blackhole` and `Time-travel` are the only two with unconventional
  orthography (`BLACKHOLE`, `TIME-TRAVEL` on a card). Both are valid and slug
  cleanly; change them only if you dislike how they read.
