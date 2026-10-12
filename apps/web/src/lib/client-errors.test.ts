import { describe, expect, it } from "vitest";

import { logLine, MAX_BYTES, RateLimit, receive } from "./client-errors";
import type { ErrorReport } from "./error-report";

const report: ErrorReport = {
  ref: "K7Q2-M9XD",
  source: "window",
  name: "TypeError",
  message: "x is undefined",
  stack: "",
  path: "/games",
  digest: null,
};

function post(body: string, headers: Record<string, string> = {}) {
  return new Request("http://web.test/api/client-errors", {
    method: "POST",
    headers: { "content-type": "application/json", ...headers },
    body,
  });
}

describe("receive", () => {
  it("takes a good report", async () => {
    const outcome = await receive(post(JSON.stringify(report)), new RateLimit());
    expect(outcome).toEqual({ status: 204, report });
  });

  it.each([
    ["cross-site", post(JSON.stringify(report), { "sec-fetch-site": "cross-site" }), 403],
    ["not JSON", post(JSON.stringify(report), { "content-type": "text/plain" }), 415],
    ["too large", post(JSON.stringify({ ...report, message: "x".repeat(MAX_BYTES) })), 413],
    ["unreadable", post("{nope"), 400],
    ["the wrong shape", post(JSON.stringify({ ...report, email: "a@b.co" })), 400],
  ])("refuses a report that's %s", async (_label, request, status) => {
    expect((await receive(request, new RateLimit())).status).toBe(status);
  });

  it("stops at the rate limit", async () => {
    const limit = new RateLimit(2);
    const statuses = [];
    for (let i = 0; i < 3; i++) {
      statuses.push((await receive(post(JSON.stringify(report)), limit)).status);
    }
    expect(statuses).toEqual([204, 204, 429]);
  });
});

describe("RateLimit", () => {
  it("starts again each minute", () => {
    let now = 0;
    const limit = new RateLimit(1, () => now);
    expect([limit.take(), limit.take()]).toEqual([true, false]);
    now = 60_000;
    expect(limit.take()).toBe(true);
  });
});

describe("logLine", () => {
  it("is one JSON line Error Reporting can group, with the reference and no person", () => {
    const line = logLine(report, "Mozilla/5.0", "web-00042-abc");
    expect(line).not.toContain("\n");
    const entry = JSON.parse(line) as Record<string, unknown>;
    expect(entry).toMatchObject({
      severity: "ERROR",
      "@type": "type.googleapis.com/google.devtools.clouderrorreporting.v1beta1.ReportedErrorEvent",
      serviceContext: { service: "web-client", version: "web-00042-abc" },
      event: "client_error",
      ref: "K7Q2-M9XD",
      path: "/games",
    });
    expect(entry.message).toBe("TypeError: x is undefined\n(ref K7Q2-M9XD)");
    expect(Object.keys(entry)).not.toContain("ip");
  });
});
