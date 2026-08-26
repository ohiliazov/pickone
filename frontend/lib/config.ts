/**
 * The frontend half of the configuration register. [SPEC §21.3]
 *
 * Every [CONFIG] value the client needs lives here with the documented default.
 * A magic number in a component is a review failure.
 */

export const config = {
  /** Public origin. Used for canonicals, Open Graph, and sitemap URLs. */
  baseUrl: process.env.NEXT_PUBLIC_BASE_URL ?? "http://localhost:3100",

  /** Where /api/* is proxied. Same-origin in production so cookies stay SameSite=Lax. */
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8100",

  /** Only production may be indexed. [SPEC §14.8] */
  env: process.env.NEXT_PUBLIC_ENV ?? "local",
} as const;

export const isIndexable = config.env === "production";

/** Motion budget. [SPEC §5.3] Tap to next pair interactive must stay under 1.1s. */
export const motion = {
  pressMs: 80,
  loserRecedeMs: 120,
  resultRevealMs: 900,
  swapMs: 180,
  skeletonAfterMs: 400,
} as const;
