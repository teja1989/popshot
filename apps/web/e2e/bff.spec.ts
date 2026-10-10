import { expect, test } from "@playwright/test";

// The /api routes forward to the API. These check what gets through and what doesn't.

interface Echo {
  method: string;
  path: string;
  query: string;
  headers: Record<string, string>;
  body: string;
}

test("requests without a token never reach the API", async ({ request }) => {
  const response = await request.get("/api/v1/me");
  expect(response.status()).toBe(401);
  expect(response.headers()["cache-control"]).toBe("no-store");
});

test("forwards only the allowed headers", async ({ request }) => {
  const response = await request.get("/api/v1/me?x=1", {
    headers: {
      authorization: "Bearer user-token",
      cookie: "session=secret",
      "x-forwarded-for": "6.6.6.6",
      "x-serverless-authorization": "Bearer forged",
      "x-custom": "nope",
    },
  });
  expect(response.status()).toBe(200);
  const echo = (await response.json()) as Echo;
  expect(echo.path).toBe("/v1/me");
  expect(echo.query).toBe("?x=1");
  expect(echo.headers.authorization).toBe("Bearer user-token");
  expect(echo.headers.cookie).toBeUndefined();
  expect(echo.headers["x-custom"]).toBeUndefined();
  // Locally there's no service identity, and a client can't inject one.
  expect(echo.headers["x-serverless-authorization"]).toBeUndefined();

  // And nothing from the API leaks back except the allowed headers.
  expect(response.headers()["set-cookie"]).toBeUndefined();
  expect(response.headers()["x-internal"]).toBeUndefined();
  expect(response.headers()["cache-control"]).toBe("no-store");
});

test("passes JSON bodies through", async ({ request }) => {
  const response = await request.post("/api/v1/matches", {
    headers: { authorization: "Bearer user-token" },
    data: { points_to: 11 },
  });
  const echo = (await response.json()) as Echo;
  expect(echo.method).toBe("POST");
  expect(JSON.parse(echo.body)).toEqual({ points_to: 11 });
  expect(echo.headers["content-type"]).toBe("application/json");
});

test("rejects non-JSON and oversized bodies", async ({ request }) => {
  const form = await request.post("/api/v1/matches", {
    headers: { authorization: "Bearer t", "content-type": "text/plain" },
    data: "hello",
  });
  expect(form.status()).toBe(415);
  const big = await request.post("/api/v1/matches", {
    headers: { authorization: "Bearer t", "content-type": "application/json" },
    data: JSON.stringify({ pad: "x".repeat(70 * 1024) }),
  });
  expect(big.status()).toBe(413);
});

test("only /api/v1 paths with plain segments are forwarded", async ({ request }) => {
  const headers = { authorization: "Bearer t" };
  for (const path of [
    "/api/v2/me",
    "/api/v1",
    "/api/healthz",
    "/api/v1/%2e%2e/admin",
    "/api/v1/a%2Fb",
    "/api/v1/me.json",
  ]) {
    const response = await request.get(path, { headers });
    expect(response.status(), path).toBe(404);
  }
});

test("refuses cross-site writes", async ({ request }) => {
  const response = await request.post("/api/v1/matches", {
    headers: { authorization: "Bearer t", "sec-fetch-site": "cross-site" },
    data: {},
  });
  expect(response.status()).toBe(403);
});

test("does not follow API redirects", async ({ request }) => {
  const response = await request.get("/api/v1/redirect", {
    headers: { authorization: "Bearer t" },
    maxRedirects: 0,
  });
  expect(response.status()).toBe(502);
});

test("passes API status codes through", async ({ request }) => {
  const response = await request.get("/api/v1/missing", { headers: { authorization: "Bearer t" } });
  expect(response.status()).toBe(404);
});
