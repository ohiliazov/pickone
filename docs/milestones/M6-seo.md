# M6 — Public SEO surfaces

**Size:** L · **Depends on:** M2, M4 · **Parallel with:** M5
**Spec reference:** [§8.3](../SPEC.md#83-items), [§8.6](../SPEC.md#86-public-non-json-routes-frontend), [§14](../SPEC.md#14-seo-architecture) in full

## Goal

Every played pair and every well-battled item becomes a real, fast, server-rendered page that a person would be happy to land on — and the system never emits a page that does not deserve to exist.

## Scope

- **`/`** per [§14.2](../SPEC.md#142-rendering-strategy): cards above the fold — a cached featured comparison rendered server-side (real text, no JS required) which the client swaps for a **live battle on mount, for any visitor including guests** — and real server-rendered content below: top 10, most-played comparisons this week, newest items.
- **Server-rendering `/` must create zero `users` rows and zero battles.** With guest play, that no longer holds by accident: guest creation happens only in the client's `GET /api/battles/current`, `robots.txt` disallows `/api/`, and the janitor reaps what a JS-rendering crawler still manages to create. **Do not add bot fingerprinting** — the false-positive cost to Googlebot and real users vastly exceeds the storage.
- **`/rankings`** and **`/rankings/page/{n}`**: server-rendered from the `item_rankings` materialised view (**RD-gated** — only ranked items appear, [§10.5](../SPEC.md#105-ranked-and-unranked--what-rd-buys-the-product)), page size 50, self-canonical per page, numeric pagination links, `noindex,follow` beyond page 100.
- **`/item/{slug}`**: rank, rating, W/L, battle count, closest rivals, biggest wins, biggest losses, most-played comparisons, recent battles, rank neighbours — all as plain `<a href>` internal links, capped at `MAX_INTERNAL_LINKS_PER_PAGE`. Ratings render **always signed** (`+487`, `−312`, `0`) with a real minus sign, and never with colour as the only encoding ([§10.4](../SPEC.md#104-zero-is-the-origin-and-the-sign-is-the-product)). An **unranked** item shows *"Still settling. 7 picks in."* in place of a rank, and is `noindex,follow` regardless of its battle count. **`rating_deviation` itself is never exposed** — only the derived `ranked` flag.
- **`/compare/{slug}`**: the pair, the split, the battle count, first/last battle, a weekly trend, links to both items, and one call to action — *Pick one yourself*.
- **Indexing thresholds** ([§14.4](../SPEC.md#144-indexing-thresholds--the-anti-thin-content-mechanism)) driving the `robots` meta tag on every page. `noindex,**follow**`, never `nofollow`.
- **Canonicals and redirects:** self-referencing canonical on every page; `301` for a reversed comparison slug, trailing slash, and uppercase; `404` for a comparison that does not exist as a row; `410` for hidden/rejected items and for comparisons involving them.
- **Metadata** ([§14.5](../SPEC.md#145-metadata)): the title/description templates with live numbers baked in, Open Graph, Twitter card.
- **OG image generation:** `/og/item/{slug}.png` and `/og/compare/{slug}.png` via `ImageResponse`, immutable-cached, with escaped and length-capped text.
- **Structured data** ([§14.6](../SPEC.md#146-structured-data)): `BreadcrumbList`, `ItemList`, `WebSite` — JSON-encoded, never string-concatenated. **No `Product`, `Review` or `AggregateRating`.**
- **Sitemaps** ([§14.7](../SPEC.md#147-sitemaps)): worker-generated every 6h to storage, index + static + rankings + chunked gzipped items and comparisons, accurate `lastmod`, comparison cap by `battle_count`.
- **`robots.txt`** ([§14.8](../SPEC.md#148-robotstxt)), environment-aware, with `Disallow: /` plus `X-Robots-Tag: noindex` on every non-production environment.
- **ISR** with the revalidation windows and `Cache-Control` headers from [§14.2](../SPEC.md#142-rendering-strategy), plus on-demand revalidation of an item page when its rank changes materially.
- The `item_rankings` materialised view and its `REFRESH … CONCURRENTLY` worker job.
- Public read API endpoints: `GET /api/rankings`, `GET /api/items/{slug}` (full payload with rivals), `GET /api/comparisons/{slug}`.
- Search Console verification and sitemap submission.

## Database changes

`item_rankings` materialised view + its two unique indexes. `comparisons_indexable_idx` if not already created in M4. No new tables.

## API changes

The three public read endpoints from [§8.3](../SPEC.md#83-items), including the `301` behaviour on a reversed comparison slug and `indexable` in the comparison payload.

## Frontend changes

All four public templates, the OG image routes, `robots.txt`, the sitemap routes, and the metadata layer.

## Tests

**The full SEO assertion suite from [§16.5](../SPEC.md#165-e2e-playwright)**, on a seeded database:
- Exactly one `<h1>`, a `<title>`, a `meta description` and a self-referencing canonical on every public template.
- `/compare/b-vs-a` → `301` → `/compare/a-vs-b`.
- `/compare/x-vs-y` for a pair with no row → `404` (not a rendered page, not a soft 404).
- 9 battles → `noindex,follow`; 10 battles → `index,follow`. Both directions, at the exact boundary.
- 4 battles on an item → `noindex,follow`; 5 → `index,follow`.
- An **unranked** item (RD above threshold) is `noindex,follow` and absent from the sitemap even with 50 battles, and its page shows the "Still settling" copy.
- No response body on any public route contains a `rating_deviation` field.
- An item at exactly `0` renders as `0` on its page, in `<title>`, in the meta description and in its OG image — **never as blank, "unrated", or missing**. This is the falsy-zero regression test.
- A negative rating renders with U+2212 in HTML and in the OG image, and the page is legible in both themes without relying on colour to convey the sign.
- A hidden item's page → `410`; a comparison involving it → `410`; both drop from the next sitemap build.
- `/rankings/page/2` is self-canonical, **not** canonicalised to page 1.
- `/rankings/page/101` → `noindex,follow`.
- Item text containing `<script>`, quotes, unicode and RTL overrides renders escaped in HTML, `<title>`, meta tags, JSON-LD **and** the OG image.
- Every JSON-LD block parses and validates against its declared type.
- No `Product`, `Review` or `AggregateRating` appears in any emitted JSON-LD — asserted by string search across all templates.
- `robots.txt` in a non-production environment contains `Disallow: /`, and the response carries `X-Robots-Tag: noindex`.
- **With JavaScript disabled**, `/item/{slug}` and `/compare/{slug}` contain the full item text and every internal link.
- An anonymous request to `/` creates **zero** battles (asserted by row count before and after).

**Sitemap:**
- Index references all children; every child is valid XML against the sitemap schema; all URLs are absolute and canonical; every URL in the sitemap returns `200` and `index,follow`; no `noindex` URL appears; the comparison file respects the cap; `lastmod` matches the entity's real last activity and is not `now()`.

**Performance:**
- Lighthouse ≥ 95 SEO and ≥ 90 performance on all four public templates.
- LCP < 2.0s and CLS < 0.05 on `/item/{slug}` and `/compare/{slug}` at a throttled mobile profile.
- `/rankings/page/50` renders in under 200ms server-side (the materialised view is doing its job).

**Accessibility:** zero `axe` violations on all four public templates, both themes.

## Acceptance criteria

1. All four public templates are fully server-rendered and complete with JavaScript disabled.
2. Indexing thresholds are enforced exactly at their configured boundaries, in both directions.
3. No route can materialise a comparison page for a pair that has never battled.
4. The sitemap contains only indexable URLs and nothing else, with accurate `lastmod`.
5. A non-production environment cannot be indexed — proven by a CI test.
6. Reversed, trailing-slash and uppercase URL variants all `301` to a single canonical.
7. OG images render correctly for 2-character and 60-character item text, and for hostile input.
8. No `AggregateRating`/`Review`/`Product` markup exists anywhere.
9. Lighthouse SEO ≥ 95 on every public template.
10. Server-rendering `/`, `/rankings`, `/item/*` and `/compare/*` creates **zero** `users` rows and **zero** battles — asserted by row counts before and after a full crawl of the seeded site.

## Non-goals

Site search, category or tag pages, user profile pages, `/rankings/{country}` or any demographic ranking (Phase 2), multilingual routes or `hreflang` (Phase 4), ads (Phase 5), comments on comparison pages, item slug redirects or aliases (nothing is renamed in MVP), AMP, RSS, a public data export, blog or editorial pages.
