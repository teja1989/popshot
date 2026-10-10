import { describe, expect, it, vi } from "vitest";

import { ServiceIdentity } from "./service-auth";

function jwt(exp: number): string {
  const payload = Buffer.from(JSON.stringify({ exp })).toString("base64url");
  return `header.${payload}.signature`;
}

describe("ServiceIdentity", () => {
  it("asks the metadata server for a token for the API audience", async () => {
    const fetchFn = vi.fn<(url: string, init?: RequestInit) => Promise<Response>>(() =>
      Promise.resolve(new Response(jwt(5000))),
    );
    const identity = new ServiceIdentity("https://api.example", fetchFn, () => 1000);
    expect(await identity.token()).toBe(jwt(5000));
    const [url, init] = fetchFn.mock.calls[0] ?? [];
    expect(url).toContain("audience=https%3A%2F%2Fapi.example");
    expect(new Headers(init?.headers).get("metadata-flavor")).toBe("Google");
  });

  it("caches until five minutes before expiry", async () => {
    let now = 1000;
    let exp = 4600;
    const fetchFn = vi.fn(() => Promise.resolve(new Response(jwt(exp))));
    const identity = new ServiceIdentity("aud", fetchFn, () => now);
    await identity.token();
    now = 4200;
    await identity.token();
    expect(fetchFn).toHaveBeenCalledTimes(1);
    now = 4400;
    exp = 8000;
    expect(await identity.token()).toBe(jwt(8000));
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  it("shares one request between concurrent callers", async () => {
    const fetchFn = vi.fn(() => Promise.resolve(new Response(jwt(9000))));
    const identity = new ServiceIdentity("aud", fetchFn, () => 1000);
    await Promise.all([identity.token(), identity.token(), identity.token()]);
    expect(fetchFn).toHaveBeenCalledTimes(1);
  });

  it("fails on a bad response", async () => {
    const identity = new ServiceIdentity(
      "aud",
      () => Promise.resolve(new Response("nope", { status: 500 })),
      () => 1000,
    );
    await expect(identity.token()).rejects.toThrow("500");
  });
});
