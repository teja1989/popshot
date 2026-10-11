import { NextResponse, type NextRequest } from "next/server";

import { readServerConfig } from "@/lib/config";
import { buildCsp, newNonce } from "@/lib/csp";

// Adds a per-request CSP nonce to every page. Next.js reads the nonce from the
// request's CSP header and stamps it on the scripts it renders.
export function proxy(request: NextRequest): NextResponse {
  const nonce = newNonce();
  const config = readServerConfig();
  const csp = buildCsp({
    nonce,
    authDomain: config.firebase.authDomain,
    dev: process.env.NODE_ENV === "development",
    authEmulatorHost: config.authEmulatorHost,
  });

  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("content-security-policy", csp);

  const response = NextResponse.next({ request: { headers: requestHeaders } });
  response.headers.set("content-security-policy", csp);
  return response;
}

export const config = {
  matcher: [
    {
      source: "/((?!api/|_next/static|_next/image|icons/|manifest.webmanifest|favicon.ico).*)",
      missing: [
        { type: "header", key: "next-router-prefetch" },
        { type: "header", key: "purpose", value: "prefetch" },
      ],
    },
  ],
};
