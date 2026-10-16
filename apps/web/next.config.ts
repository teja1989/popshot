import type { NextConfig } from "next";

// Headers for every response, including API routes and static files. The page CSP
// (with its per-request nonce) is added in src/proxy.ts.
const securityHeaders = [
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Firebase's Google sign-in popup needs to talk back to this window.
  { key: "Cross-Origin-Opener-Policy", value: "same-origin-allow-popups" },
  { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(self), payment=(), usb=(), interest-cohort=(), browsing-topics=()",
  },
];

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  // Don't let `next dev` write an AGENTS.md into the repo.
  agentRules: false,
  // Browsers and other clients ask for /favicon.ico even when a page names its icon.
  // Old addresses land in the right place. The Games tab became Play (old links and
  // notifications keep their ?logged= and ?reflect=).
  async redirects() {
    return [
      { source: "/games", destination: "/play", permanent: true },
      // More became You → Settings (docs/adr/0006-navigation.md). Not permanent: the menu may
      // still change before the apps.
      { source: "/more", destination: "/you/settings", permanent: false },
    ];
  },
  async rewrites() {
    return [{ source: "/favicon.ico", destination: "/icons/192" }];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
