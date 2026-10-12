import { describe, expect, it, vi, type Mock } from "vitest";

import { fetchSharedRecap } from "./shared-recap";

const TOKEN = "A".repeat(43);
const config = { apiBaseUrl: new URL("http://127.0.0.1:4010"), apiAudience: "https://api.example" };

type FetchFn = (url: URL, init: RequestInit) => Promise<Response>;

function api(status: number, body: unknown = {}): Mock<FetchFn> {
  return vi.fn<FetchFn>(() => Promise.resolve(Response.json(body, { status })));
}

describe("fetchSharedRecap", () => {
  it("posts the token in the body with the web service's identity", async () => {
    const fetchFn = api(200, { crew: "Lunch Dinkers" });
    const recap = await fetchSharedRecap(TOKEN, {
      config,
      fetchFn: fetchFn as unknown as typeof fetch,
      token: () => Promise.resolve("service-token"),
    });
    expect(recap?.crew).toBe("Lunch Dinkers");
    const [url, init] = fetchFn.mock.calls[0] ?? [];
    expect(url?.toString()).toBe("http://127.0.0.1:4010/v1/public/recap");
    expect(url?.toString()).not.toContain(TOKEN);
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe(JSON.stringify({ token: TOKEN }));
    const headers = new Headers(init?.headers);
    expect(headers.get("x-serverless-authorization")).toBe("Bearer service-token");
    expect(headers.get("authorization")).toBeNull();
  });

  it("is null for a dead link and never calls the API for a malformed one", async () => {
    const fetchFn = api(404);
    const deps = { config, fetchFn: fetchFn as unknown as typeof fetch, token: () => null };
    expect(await fetchSharedRecap(TOKEN, deps)).toBeNull();
    for (const bad of ["", "short", `${"A".repeat(42)}/`, "../v1/me" + "A".repeat(35)]) {
      expect(await fetchSharedRecap(bad, deps)).toBeNull();
    }
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it("throws on other failures, so the error screen shows", async () => {
    const deps = { config, fetchFn: api(500) as unknown as typeof fetch, token: () => null };
    await expect(fetchSharedRecap(TOKEN, deps)).rejects.toThrow("500");
  });
});
