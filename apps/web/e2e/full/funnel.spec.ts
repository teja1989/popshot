import { expect, test } from "@playwright/test";

import { newUser, signIn } from "./auth";
import { watchProblems } from "./problems";

test("a tagged link is counted, remembered, and sent once at sign-up", async ({ page }) => {
  // Signed out, on the home page from a tagged link: one anonymous visit.
  const visit = page.waitForResponse((r) => r.url().endsWith("/api/visit"));
  await page.goto("/?src=reddit");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  expect((await visit).status()).toBe(204);
  expect(await page.evaluate(() => localStorage.getItem("popshot.source"))).toBe("reddit");

  // Signing up sends it, and the browser forgets it.
  await signIn(page, newUser("Rae"));
  const problems = await watchProblems(page);
  const sent = page.waitForResponse((r) => r.url().endsWith("/api/v1/me/source"));
  await page.goto("/");
  const response = await sent;
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ recorded: true });
  await expect.poll(() => page.evaluate(() => localStorage.getItem("popshot.source"))).toBeNull();

  // It's in your data download.
  await page.goto("/you");
  const download = page.waitForEvent("download");
  await page.getByRole("region", { name: "Your data" }).getByRole("button", { name: "Download my data" }).click();
  const file = await (await download).path();
  const { readFile } = await import("node:fs/promises");
  expect((JSON.parse(await readFile(file, "utf8")) as { signup_source: string }).signup_source).toBe("reddit");
  expect(problems).toEqual([]);
});

test("the browser can't reach the API's public routes, even with a made-up sign-in", async ({ request }) => {
  for (const path of ["/api/v1/public/visits", "/api/v1/public/recap"]) {
    const response = await request.post(path, {
      headers: { authorization: "Bearer made-up" },
      data: { page: "home", source: "direct" },
    });
    expect(response.status()).toBe(404);
  }
  // Only known pages and sources get through the web's own counter.
  expect((await request.post("/api/visit", { data: { page: "admin", source: "direct" } })).status()).toBe(400);
});
