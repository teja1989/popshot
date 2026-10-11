import { expect, test } from "@playwright/test";

import { newUser, signIn } from "./auth";

test("a signed-in user lands on their home, with their profile from the API", async ({ page }) => {
  const alice = newUser("Alice");
  await signIn(page, alice);

  // Watch the app page only (signIn's setup page is a bare image, which the browser
  // follows with a request for /favicon.ico).
  const problems: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      problems.push(message.text());
    }
  });
  page.on("pageerror", (error) => problems.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 400) {
      problems.push(`${String(response.status())} ${response.url()}`);
    }
  });
  await page.goto("/");

  // The name comes back through web -> API -> Postgres, not from the browser's session.
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(`Hi, ${alice.name}.`);
  await expect(page.getByText("You're signed in.")).toBeVisible();
  expect(problems).toEqual([]);
});

test("signing out returns to the sign-in screen and stays signed out", async ({ page }) => {
  await signIn(page, newUser("Bob"));
  await page.goto("/");
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("button", { name: "Continue with Google" })).toBeVisible();
});

test("the API rejects a request without a token, even with a session in the browser", async ({
  page,
}) => {
  await signIn(page, newUser("Cara"));
  const status = await page.evaluate(async () => (await fetch("/api/v1/me")).status);
  expect(status).toBe(401);
});
