// Forwards browser requests from /api/v1/... to the private API.
//
// The browser never talks to the API directly. This layer is deliberately dumb: it doesn't
// decide who the user is (the API verifies the ID token itself), it only passes a small,
// fixed set of headers through and adds the web service's own identity on Cloud Run.

import type { Upstream } from "./config";

const ALLOWED_METHODS = new Set(["GET", "POST", "PUT", "PATCH", "DELETE"]);
const SAFE_METHODS = new Set(["GET"]);
const SEGMENT = /^[A-Za-z0-9_-]{1,64}$/;
const MAX_SEGMENTS = 8;
const MAX_BODY_BYTES = 64 * 1024;
const MAX_AUTH_HEADER = 8192;
const TIMEOUT_MS = 10_000;
const TRACE = /^[0-9a-f]{32}(\/\d{1,20})?(;o=[01])?$/;

export interface ForwardDeps {
  apiBaseUrl: URL;
  serviceToken: (() => Promise<string>) | null;
  fetchFn?: typeof fetch;
}

function problem(status: number, detail: string): Response {
  return Response.json(
    { detail },
    { status, headers: { "cache-control": "no-store", "x-content-type-options": "nosniff" } },
  );
}

/**
 * Which service a path goes to: /v1/admin/... to the admin service (its own identity and
 * database login), everything else to the API. Null when the admin service isn't set up.
 */
export function upstreamFor(
  segments: readonly string[],
  config: { apiBaseUrl: URL; apiAudience: string | null; adminApi: Upstream | null },
): Upstream | null {
  if (segments[0] === "v1" && segments[1] === "admin") {
    return config.adminApi;
  }
  return { baseUrl: config.apiBaseUrl, audience: config.apiAudience };
}

export function upstreamPath(segments: readonly string[]): string | null {
  if (segments.length < 2 || segments.length > MAX_SEGMENTS || segments[0] !== "v1") {
    return null;
  }
  // /v1/public/... is for the web server only (shared recap cards, visit counts), never
  // forwarded from a browser: it takes no sign-in, so the proxy's bearer check means nothing.
  if (segments[1] === "public") {
    return null;
  }
  // Next.js has already decoded each segment, so "%2F" or ".." would show up here.
  if (!segments.every((s) => SEGMENT.test(s))) {
    return null;
  }
  return "/" + segments.join("/");
}

async function readBody(request: Request): Promise<ArrayBuffer | null | "too-large"> {
  const declared = Number(request.headers.get("content-length") ?? "0");
  if (declared > MAX_BODY_BYTES) {
    return "too-large";
  }
  if (!request.body) {
    return null;
  }
  const body = await request.arrayBuffer();
  if (body.byteLength > MAX_BODY_BYTES) {
    return "too-large";
  }
  return body.byteLength === 0 ? null : body;
}

export async function forward(request: Request, segments: readonly string[], deps: ForwardDeps): Promise<Response> {
  const method = request.method.toUpperCase();
  if (!ALLOWED_METHODS.has(method)) {
    return problem(405, "Method not allowed.");
  }
  const path = upstreamPath(segments);
  if (path === null) {
    return problem(404, "Not found.");
  }
  // Defense in depth: the bearer header already stops classic CSRF, but refuse
  // cross-site state changes outright.
  if (!SAFE_METHODS.has(method) && request.headers.get("sec-fetch-site") === "cross-site") {
    return problem(403, "Cross-site requests are not allowed.");
  }

  const authorization = request.headers.get("authorization");
  if (
    !authorization?.startsWith("Bearer ") ||
    authorization.length > MAX_AUTH_HEADER ||
    authorization.length <= "Bearer ".length
  ) {
    return problem(401, "Sign in to continue.");
  }

  const headers = new Headers({ authorization, accept: "application/json" });
  const trace = request.headers.get("x-cloud-trace-context");
  if (trace && TRACE.test(trace)) {
    headers.set("x-cloud-trace-context", trace);
  }

  let body: ArrayBuffer | null = null;
  if (!SAFE_METHODS.has(method)) {
    const contentType = request.headers.get("content-type");
    const read = await readBody(request);
    if (read === "too-large") {
      return problem(413, "That request is too large.");
    }
    if (read !== null) {
      if (!contentType?.toLowerCase().startsWith("application/json")) {
        return problem(415, "Send JSON.");
      }
      headers.set("content-type", "application/json");
      body = read;
    }
  }

  if (deps.serviceToken) {
    try {
      headers.set("x-serverless-authorization", `Bearer ${await deps.serviceToken()}`);
    } catch {
      return problem(502, "Popshot is having trouble right now. Try again in a moment.");
    }
  }

  const target = new URL(path, deps.apiBaseUrl);
  target.search = new URL(request.url).search;

  let upstream: Response;
  try {
    upstream = await (deps.fetchFn ?? fetch)(target, {
      method,
      headers,
      body,
      redirect: "manual",
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  } catch {
    return problem(502, "Popshot is having trouble right now. Try again in a moment.");
  }

  if (upstream.status >= 300 && upstream.status < 400) {
    return problem(502, "Popshot is having trouble right now. Try again in a moment.");
  }

  const responseHeaders = new Headers({
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
  });
  for (const name of ["content-type", "www-authenticate", "retry-after"]) {
    const value = upstream.headers.get(name);
    if (value) {
      responseHeaders.set(name, value);
    }
  }
  return new Response(upstream.body, { status: upstream.status, headers: responseHeaders });
}
