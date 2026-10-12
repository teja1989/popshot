// Crash reports from the browser: what's sent, how it's cleaned, and the short reference
// people can quote to support. Shared by the browser (lib/report-error.ts) and the server
// route that logs them (app/api/client-errors), which checks and cleans everything again.
//
// No user ID, name or email goes in a report. Messages and stacks are scrubbed of anything
// that looks like an email, a token or an ID, and URLs lose their query and fragment (an
// invite link's token lives in the fragment).

export const ERROR_SOURCES = ["page", "app", "window", "promise"] as const;
export type ErrorSource = (typeof ERROR_SOURCES)[number];

export interface ErrorReport {
  ref: string;
  source: ErrorSource;
  name: string;
  message: string;
  stack: string;
  path: string;
  // Next.js's ID for an error thrown while rendering on the server, logged there too.
  digest: string | null;
}

export const LIMITS = { name: 80, message: 500, stack: 3000, path: 200, digest: 64 } as const;

// Crockford base32: no I, L, O or U, so it reads aloud and types back without mix-ups.
const REF_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
export const REF_PATTERN = /^[0-9A-HJKMNP-TV-Z]{4}-[0-9A-HJKMNP-TV-Z]{4}$/;

export function newErrorRef(randomBytes: (n: number) => Uint8Array = (n) => crypto.getRandomValues(new Uint8Array(n))) {
  const chars = Array.from(randomBytes(8), (byte) => REF_ALPHABET.charAt(byte % 32));
  return `${chars.slice(0, 4).join("")}-${chars.slice(4).join("")}`;
}

const UUID = /\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi;
const EMAIL = /[^\s@"'<>()]+@[^\s@"'<>()]+\.[a-z]{2,}/gi;
// A URL keeps its origin and path; its query and fragment go.
const URL_TAIL = /(https?:\/\/[^\s?#"'<>]*)[?#][^\s"'<>)]*/gi;
// Long runs of token-ish characters: invite tokens, JWTs, keys.
const TOKEN = /[A-Za-z0-9_\-.+/=]{32,}/g;
const CONTROL = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g;

export function scrub(text: string, max: number): string {
  return text
    .replace(CONTROL, "")
    .replace(URL_TAIL, "$1")
    .replace(EMAIL, "[email]")
    .replace(UUID, ":id")
    .replace(TOKEN, (match) => (/^[A-Za-z0-9_\-./]+\.(js|ts|tsx|css|map)$/.test(match) ? match : "[token]"))
    .slice(0, max);
}

/** A page's path with IDs replaced, so reports group by page and say nothing about whose. */
export function cleanPath(pathname: string): string {
  const path = pathname.split(/[?#]/)[0] ?? "/";
  return scrub(path.startsWith("/") ? path : `/${path}`, LIMITS.path);
}

function text(value: unknown, max: number): string | null {
  return typeof value === "string" ? scrub(value, max) : null;
}

/** A report as received: exactly the expected fields and types, cleaned, or null. */
export function parseReport(value: unknown): ErrorReport | null {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return null;
  }
  const raw = value as Record<string, unknown>;
  const allowed = new Set(["ref", "source", "name", "message", "stack", "path", "digest"]);
  if (Object.keys(raw).some((key) => !allowed.has(key))) {
    return null;
  }
  const { ref, source, digest } = raw;
  if (typeof ref !== "string" || !REF_PATTERN.test(ref)) {
    return null;
  }
  if (typeof source !== "string" || !(ERROR_SOURCES as readonly string[]).includes(source)) {
    return null;
  }
  const name = text(raw.name, LIMITS.name);
  const message = text(raw.message, LIMITS.message);
  const stack = text(raw.stack, LIMITS.stack);
  const path = typeof raw.path === "string" ? cleanPath(raw.path) : null;
  if (name === null || message === null || stack === null || path === null) {
    return null;
  }
  if (digest !== null && digest !== undefined && (typeof digest !== "string" || !/^[\w-]{1,64}$/.test(digest))) {
    return null;
  }
  return { ref, source: source as ErrorSource, name, message, stack, path, digest: digest ?? null };
}
