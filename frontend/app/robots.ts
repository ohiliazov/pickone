import type { MetadataRoute } from "next";
import { config, isIndexable } from "@/lib/config";

/**
 * [SPEC §14.8] Staging and preview serve Disallow: / — verified in CI, because
 * an indexed preview deploy is the classic own-goal.
 */
export default function robots(): MetadataRoute.Robots {
  if (!isIndexable) {
    return { rules: [{ userAgent: "*", disallow: "/" }] };
  }
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: ["/api/", "/admin", "/play", "/add", "/login", "/register", "/verify", "/reset", "/*?"],
      },
    ],
    sitemap: `${config.baseUrl}/sitemap.xml`,
  };
}
