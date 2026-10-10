import { expect, test } from "@playwright/test";

test("home page renders with a strict, nonce-based CSP and no violations", async ({ page }) => {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      problems.push(message.text());
    }
  });
  page.on("pageerror", (error) => problems.push(error.message));
  const external: string[] = [];
  page.on("request", (request) => {
    if (!request.url().startsWith("http://127.0.0.1:3100/")) {
      external.push(request.url());
    }
  });
  await page.addInitScript(() => {
    document.addEventListener("securitypolicyviolation", (event) => {
      console.error(`CSP violation: ${event.violatedDirective} ${event.blockedURI}`);
    });
  });

  const response = await page.goto("/");
  expect(response?.status()).toBe(200);

  const csp = response?.headers()["content-security-policy"] ?? "";
  const scriptSrc = /script-src ([^;]+)/.exec(csp)?.[1] ?? "";
  expect(scriptSrc).toMatch(/'nonce-[A-Za-z0-9+/=]{16,}'/);
  expect(scriptSrc).toContain("'strict-dynamic'");
  expect(scriptSrc).not.toContain("'unsafe-inline'");
  expect(scriptSrc).not.toContain("'unsafe-eval'");
  expect(csp).toContain("object-src 'none'");
  expect(csp).toContain("frame-ancestors 'none'");
  expect(csp).toContain("frame-src https://popshot-test.firebaseapp.com");

  // Every script in the server-rendered HTML carries this request's nonce. Chunks that
  // those scripts load later are allowed through 'strict-dynamic' instead.
  const nonce = /'nonce-([^']+)'/.exec(scriptSrc)?.[1] ?? "missing";
  // Parse with the browser's own HTML parser rather than a regex, so no spelling or
  // casing of a script tag can slip past.
  const html = (await response?.text()) ?? "";
  const scriptNonces = await page.evaluate(
    (source) =>
      Array.from(
        new DOMParser().parseFromString(source, "text/html").querySelectorAll("script"),
        (script) => script.getAttribute("nonce"),
      ),
    html,
  );
  expect(scriptNonces.length).toBeGreaterThan(0);
  for (const value of scriptNonces) {
    expect(value).toBe(nonce);
  }

  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    "Your crew's games, kept between you.",
  );
  await expect(page.getByRole("button", { name: "Sign in with Google" })).toBeEnabled();
  await page.waitForLoadState("networkidle");
  expect(problems).toEqual([]);
  // Nothing third-party loads until someone chooses to sign in.
  expect(external).toEqual([]);
});

test("each page load gets a different nonce", async ({ request }) => {
  const first = (await request.get("/")).headers()["content-security-policy"];
  const second = (await request.get("/")).headers()["content-security-policy"];
  expect(first).toBeTruthy();
  expect(first).not.toEqual(second);
});

test("security headers are set", async ({ request }) => {
  for (const path of ["/", "/api/v1/me", "/manifest.webmanifest"]) {
    const headers = (await request.get(path)).headers();
    expect(headers["strict-transport-security"]).toContain("max-age=");
    expect(headers["x-content-type-options"]).toBe("nosniff");
    expect(headers["x-frame-options"]).toBe("DENY");
    expect(headers["referrer-policy"]).toBe("strict-origin-when-cross-origin");
    expect(headers["x-powered-by"]).toBeUndefined();
  }
});

test("manifest makes the app installable", async ({ request }) => {
  const response = await request.get("/manifest.webmanifest");
  expect(response.ok()).toBe(true);
  const manifest = (await response.json()) as {
    name: string;
    start_url: string;
    display: string;
    icons: { src: string; sizes: string; type: string }[];
  };
  expect(manifest.name).toBe("Popshot");
  expect(manifest.display).toBe("standalone");
  expect(manifest.start_url).toBe("/");
  const sizes = manifest.icons.map((icon) => icon.sizes);
  expect(sizes).toContain("192x192");
  expect(sizes).toContain("512x512");
  for (const icon of manifest.icons) {
    const image = await request.get(icon.src);
    expect(image.ok()).toBe(true);
    expect(image.headers()["content-type"]).toBe("image/png");
  }
});

test("unknown pages get a friendly 404 that also follows the CSP", async ({ page }) => {
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error" && !message.text().includes("404")) {
      problems.push(message.text());
    }
  });
  const response = await page.goto("/no-such-page");
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("That page is out of bounds.");
  await page.getByRole("link", { name: "Back to Popshot" }).click();
  await expect(page).toHaveURL("/");
  expect(problems).toEqual([]);
});
