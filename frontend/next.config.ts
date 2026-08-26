import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output keeps the Pi image small and removes the need for
  // node_modules at runtime.
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  // SPEC §13.2 — the full header set lands in M7. These two are free now and
  // there is no reason to ship a preview without them.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
