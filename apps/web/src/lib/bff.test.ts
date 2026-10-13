import { describe, expect, it, vi } from "vitest";

import { forward, upstreamFor, upstreamPath } from "./bff";

const API = new URL("https://api.internal.example/");

function okFetch() {
  return vi.fn<typeof fetch>(() =>
    Promise.resolve(
      new Response('{"ok":true}', {
        status: 200,
        headers: { "content-type": "application/json", "set-cookie": "x=1" },
      }),
    ),
  );
}

function sentHeaders(fetchFn: ReturnType<typeof okFetch>): Headers {
  const init = fetchFn.mock.calls[0]?.[1];
  return new Headers(init?.headers);
}

describe("upstreamFor", () => {
  const api = new URL("https://api.example.com");
  const admin = { baseUrl: new URL("https://admin.example.com"), audience: "https://admin.example.com" };

  it("sends /v1/admin/... to the admin service and the rest to the API", () => {
    const config = { apiBaseUrl: api, apiAudience: "https://api.example.com", adminApi: admin };
    expect(upstreamFor(["v1", "admin", "overview"], config)).toBe(admin);
    expect(upstreamFor(["v1", "groups"], config)).toEqual({ baseUrl: api, audience: "https://api.example.com" });
    // Only the second segment counts: a group called "admin" is still the API's.
    expect(upstreamFor(["v1", "groups", "admin"], config)?.baseUrl).toBe(api);
  });

  it("has nowhere to send admin paths when there's no admin service", () => {
    expect(upstreamFor(["v1", "admin", "overview"], { apiBaseUrl: api, apiAudience: null, adminApi: null })).toBeNull();
  });
});

describe("upstreamPath", () => {
  it.each([
    [["v1", "me"], "/v1/me"],
    [["v1", "groups", "abc-123", "matches"], "/v1/groups/abc-123/matches"],
  ])("accepts %j", (segments, expected) => {
    expect(upstreamPath(segments)).toBe(expected);
  });

  it.each([
    [[]],
    [["v1"]],
    [["v2", "me"]],
    [["v1", ".."]],
    [["v1", "a/b"]],
    [["v1", "me.json"]],
    [["v1", ""]],
    [["v1", "a".repeat(65)]],
    [["v1", "a", "b", "c", "d", "e", "f", "g", "h"]],
    [["v1", "public", "visits"]],
    [["v1", "public", "recap"]],
  ])("rejects %j", (segments) => {
    expect(upstreamPath(segments)).toBeNull();
  });
});

describe("forward", () => {
  it("requires a bearer token and never calls the API without one", async () => {
    const fetchFn = okFetch();
    for (const auth of [null, "Basic abc", "Bearer ", "Bearer " + "x".repeat(9000)]) {
      const headers = auth ? { authorization: auth } : undefined;
      const request = new Request("https://web.example/api/v1/me", { headers });
      const response = await forward(request, ["v1", "me"], { apiBaseUrl: API, serviceToken: null, fetchFn });
      expect(response.status).toBe(401);
    }
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("forwards only allowed headers and adds the service identity", async () => {
    const fetchFn = okFetch();
    const request = new Request("https://web.example/api/v1/me?a=1", {
      headers: {
        authorization: "Bearer user",
        cookie: "s=1",
        "x-serverless-authorization": "Bearer forged",
        "x-cloud-trace-context": "0123456789abcdef0123456789abcdef/1;o=1",
        host: "evil.example",
      },
    });
    const response = await forward(request, ["v1", "me"], {
      apiBaseUrl: API,
      serviceToken: () => Promise.resolve("svc-token"),
      fetchFn,
    });
    expect(response.status).toBe(200);
    const target = fetchFn.mock.calls[0]?.[0];
    expect(target instanceof URL ? target.href : target).toBe("https://api.internal.example/v1/me?a=1");
    const sent = sentHeaders(fetchFn);
    expect([...sent.keys()].sort()).toEqual([
      "accept",
      "authorization",
      "x-cloud-trace-context",
      "x-serverless-authorization",
    ]);
    expect(sent.get("authorization")).toBe("Bearer user");
    expect(sent.get("x-serverless-authorization")).toBe("Bearer svc-token");
    expect(fetchFn.mock.calls[0]?.[1]?.redirect).toBe("manual");
    expect(response.headers.get("set-cookie")).toBeNull();
    expect(response.headers.get("cache-control")).toBe("no-store");
  });

  it("drops a malformed trace header", async () => {
    const fetchFn = okFetch();
    const request = new Request("https://web.example/api/v1/me", {
      headers: { authorization: "Bearer u", "x-cloud-trace-context": '"},{"injected":1' },
    });
    await forward(request, ["v1", "me"], { apiBaseUrl: API, serviceToken: null, fetchFn });
    expect(sentHeaders(fetchFn).has("x-cloud-trace-context")).toBe(false);
  });

  it("returns 502 when the service identity can't be fetched", async () => {
    const fetchFn = okFetch();
    const request = new Request("https://web.example/api/v1/me", {
      headers: { authorization: "Bearer u" },
    });
    const response = await forward(request, ["v1", "me"], {
      apiBaseUrl: API,
      serviceToken: () => Promise.reject(new Error("no metadata server")),
      fetchFn,
    });
    expect(response.status).toBe(502);
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("returns 502 when the API is unreachable", async () => {
    const fetchFn = vi.fn<typeof fetch>(() => Promise.reject(new TypeError("connect refused")));
    const request = new Request("https://web.example/api/v1/me", {
      headers: { authorization: "Bearer u" },
    });
    const response = await forward(request, ["v1", "me"], { apiBaseUrl: API, serviceToken: null, fetchFn });
    expect(response.status).toBe(502);
  });

  it("refuses cross-site writes but allows same-origin ones", async () => {
    const fetchFn = okFetch();
    const make = (site: string) =>
      new Request("https://web.example/api/v1/matches", {
        method: "POST",
        headers: { authorization: "Bearer u", "sec-fetch-site": site, "content-type": "application/json" },
        body: "{}",
      });
    const deps = { apiBaseUrl: API, serviceToken: null, fetchFn };
    expect((await forward(make("cross-site"), ["v1", "matches"], deps)).status).toBe(403);
    expect((await forward(make("same-origin"), ["v1", "matches"], deps)).status).toBe(200);
  });

  it("rejects unknown methods", async () => {
    const request = new Request("https://web.example/api/v1/me", {
      method: "OPTIONS",
      headers: { authorization: "Bearer u" },
    });
    const response = await forward(request, ["v1", "me"], {
      apiBaseUrl: API,
      serviceToken: null,
      fetchFn: okFetch(),
    });
    expect(response.status).toBe(405);
  });
});
