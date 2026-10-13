// The server side of anonymous visit counts (app/api/visit): checks a beacon, limits how
// often one address and the whole instance can add to the counts, and passes it to the
// private API (/v1/public/visits, which the browser can't reach through /api).

import { RateLimit } from "./client-errors";
import type { ServerConfig } from "./config";
import { isSource, isVisitPage, type Source, type VisitPage } from "./funnel";
import { ServiceIdentity } from "./service-auth";

const MAX_BYTES = 256;
const TIMEOUT_MS = 4000;
// Per address, a minute: a person opening a few pages, never a flood.
const PER_ADDRESS = 20;
// Addresses remembered at once; past this the oldest minute's entries are dropped.
const MAX_ADDRESSES = 5000;
// The whole instance, a minute.
const PER_INSTANCE = 600;

export interface Visit {
  page: VisitPage;
  source: Source;
}

/** `limit` takes a minute per key, remembering at most `maxKeys` keys at once. */
export class KeyedRateLimit {
  private windowStart = 0;
  private counts = new Map<string, number>();

  constructor(
    private readonly limit = PER_ADDRESS,
    private readonly maxKeys = MAX_ADDRESSES,
    private readonly now: () => number = Date.now,
  ) {}

  take(key: string): boolean {
    const now = this.now();
    if (now - this.windowStart >= 60_000 || this.counts.size >= this.maxKeys) {
      this.windowStart = now;
      this.counts.clear();
    }
    const count = (this.counts.get(key) ?? 0) + 1;
    this.counts.set(key, count);
    return count <= this.limit;
  }
}

export class VisitLimits {
  constructor(
    readonly perAddress = new KeyedRateLimit(),
    readonly perInstance = new RateLimit(PER_INSTANCE),
  ) {}
}

/**
 * Who's asking, for the per-address limit: Cloud Run appends the caller's address to
 * X-Forwarded-For, so the last entry is the one a browser can't choose. Anything odd counts
 * as one shared "unknown" key, which only makes the limit stricter.
 */
export function clientKey(headers: Headers): string {
  const last = headers.get("x-forwarded-for")?.split(",").at(-1)?.trim() ?? "";
  return /^[0-9a-f.:]{2,45}$/i.test(last) ? last : "unknown";
}

export type VisitOutcome = { status: 204; visit: Visit } | { status: 400 | 403 | 413 | 429; detail: string };

export async function receiveVisit(request: Request, limits: VisitLimits): Promise<VisitOutcome> {
  if (request.headers.get("sec-fetch-site") === "cross-site") {
    return { status: 403, detail: "Cross-site requests are not allowed." };
  }
  if (Number(request.headers.get("content-length") ?? "0") > MAX_BYTES) {
    return { status: 413, detail: "Too large." };
  }
  const text = await request.text();
  if (text.length > MAX_BYTES) {
    return { status: 413, detail: "Too large." };
  }
  let body: unknown;
  try {
    body = JSON.parse(text);
  } catch {
    return { status: 400, detail: "Not valid." };
  }
  const { page, source } = (body ?? {}) as Record<string, unknown>;
  if (!isVisitPage(page) || !isSource(source)) {
    return { status: 400, detail: "Not valid." };
  }
  if (!limits.perAddress.take(clientKey(request.headers)) || !limits.perInstance.take()) {
    return { status: 429, detail: "Too many." };
  }
  return { status: 204, visit: { page, source } };
}

let identity: ServiceIdentity | null = null;

function serviceToken(audience: string | null): Promise<string> | null {
  if (audience === null) {
    return null;
  }
  identity ??= new ServiceIdentity(audience);
  return identity.token();
}

export interface ForwardVisitDeps {
  config: Pick<ServerConfig, "apiBaseUrl" | "apiAudience">;
  fetchFn?: typeof fetch;
  token?: (audience: string | null) => Promise<string> | null;
}

/** Hand the visit to the API. Throws if the API refuses, so the caller can log it. */
export async function forwardVisit(visit: Visit, deps: ForwardVisitDeps): Promise<void> {
  const headers = new Headers({ "content-type": "application/json" });
  const service = (deps.token ?? serviceToken)(deps.config.apiAudience);
  if (service !== null) {
    headers.set("x-serverless-authorization", `Bearer ${await service}`);
  }
  const response = await (deps.fetchFn ?? fetch)(new URL("/v1/public/visits", deps.config.apiBaseUrl), {
    method: "POST",
    headers,
    body: JSON.stringify(visit),
    redirect: "manual",
    cache: "no-store",
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (!response.ok) {
    throw new Error(`visit: API returned ${String(response.status)}`);
  }
}
