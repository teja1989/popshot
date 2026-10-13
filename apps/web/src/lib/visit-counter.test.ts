import { describe, expect, it } from "vitest";

import { RateLimit } from "./client-errors";
import { clientKey, forwardVisit, KeyedRateLimit, receiveVisit, VisitLimits } from "./visit-counter";

function post(body: string, headers: Record<string, string> = {}): Request {
  return new Request("https://p.example/api/visit", {
    method: "POST",
    headers: { "content-type": "application/json", "x-forwarded-for": "203.0.113.7", ...headers },
    body,
  });
}

const GOOD = JSON.stringify({ page: "home", source: "reddit" });

describe("receiveVisit", () => {
  it("takes a known page and source", async () => {
    expect(await receiveVisit(post(GOOD), new VisitLimits())).toEqual({
      status: 204,
      visit: { page: "home", source: "reddit" },
    });
  });

  it.each([
    [JSON.stringify({ page: "admin", source: "direct" })],
    [JSON.stringify({ page: "home", source: "https://evil.example" })],
    [JSON.stringify({ page: "home" })],
    ["null"],
    ["not json"],
  ])("refuses %s", async (body) => {
    expect((await receiveVisit(post(body), new VisitLimits())).status).toBe(400);
  });

  it("refuses big bodies and other sites", async () => {
    const limits = new VisitLimits();
    expect((await receiveVisit(post("x".repeat(400)), limits)).status).toBe(413);
    expect((await receiveVisit(post(GOOD, { "sec-fetch-site": "cross-site" }), limits)).status).toBe(403);
  });

  it("limits one address, not everyone", async () => {
    const limits = new VisitLimits(new KeyedRateLimit(2), new RateLimit(100));
    const statuses = [];
    for (let i = 0; i < 3; i += 1) {
      statuses.push((await receiveVisit(post(GOOD), limits)).status);
    }
    expect(statuses).toEqual([204, 204, 429]);
    // Someone else still gets through.
    expect((await receiveVisit(post(GOOD, { "x-forwarded-for": "198.51.100.9" }), limits)).status).toBe(204);
  });

  it("limits the whole instance too", async () => {
    const limits = new VisitLimits(new KeyedRateLimit(100), new RateLimit(1));
    expect((await receiveVisit(post(GOOD), limits)).status).toBe(204);
    expect((await receiveVisit(post(GOOD, { "x-forwarded-for": "198.51.100.9" }), limits)).status).toBe(429);
  });
});

describe("clientKey", () => {
  it("uses the address Cloud Run added, not what the browser sent", () => {
    expect(clientKey(new Headers({ "x-forwarded-for": "1.2.3.4, 203.0.113.7" }))).toBe("203.0.113.7");
    expect(clientKey(new Headers({ "x-forwarded-for": "2001:db8::1" }))).toBe("2001:db8::1");
  });

  it("treats anything odd as one shared key", () => {
    expect(clientKey(new Headers())).toBe("unknown");
    expect(clientKey(new Headers({ "x-forwarded-for": "<script>" }))).toBe("unknown");
  });
});

describe("KeyedRateLimit", () => {
  it("starts again each minute and stays small", () => {
    let now = 0;
    const limit = new KeyedRateLimit(1, 2, () => now);
    expect([limit.take("a"), limit.take("a")]).toEqual([true, false]);
    now = 60_000;
    expect(limit.take("a")).toBe(true);
    // A third address clears the table rather than growing it.
    expect([limit.take("b"), limit.take("c"), limit.take("a")]).toEqual([true, true, true]);
  });
});

describe("forwardVisit", () => {
  const config = { apiBaseUrl: new URL("https://api.internal"), apiAudience: "https://api.internal" };

  it("posts to the API's public route as the web service", async () => {
    const calls: [string, RequestInit][] = [];
    await forwardVisit(
      { page: "recap", source: "direct" },
      {
        config,
        token: () => Promise.resolve("svc-token"),
        fetchFn: (url, init) => {
          calls.push([url instanceof URL ? url.href : url instanceof Request ? url.url : url, init ?? {}]);
          return Promise.resolve(new Response(null, { status: 204 }));
        },
      },
    );
    const [url, init] = calls[0] ?? ["", {}];
    expect(url).toBe("https://api.internal/v1/public/visits");
    expect(new Headers(init.headers).get("x-serverless-authorization")).toBe("Bearer svc-token");
    expect(JSON.parse(init.body as string)).toEqual({ page: "recap", source: "direct" });
  });

  it("throws when the API says no", async () => {
    await expect(
      forwardVisit(
        { page: "home", source: "direct" },
        { config, token: () => null, fetchFn: () => Promise.resolve(new Response(null, { status: 500 })) },
      ),
    ).rejects.toThrow("500");
  });
});
