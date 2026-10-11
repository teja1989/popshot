import { expect, test } from "@playwright/test";

import { newUser, signIn } from "./auth";
import { watchProblems } from "./problems";

test("a signed-in user lands on their home, with their profile from the API", async ({ page }) => {
  const alice = newUser("Alice");
  await signIn(page, alice);

  const problems = await watchProblems(page);
  await page.goto("/");

  // The name comes back through web -> API -> Postgres, not from the browser's session.
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(
    /^Good (morning|afternoon|evening), Alice\.$/,
  );
  await expect(page.getByRole("heading", { name: "Your stats" })).toBeVisible();
  await expect(page.getByText("No groups yet.")).toBeVisible();
  expect(problems).toEqual([]);
});

test("signing out returns to the sign-in screen and stays signed out", async ({ page }) => {
  await signIn(page, newUser("Bob"));
  await page.goto("/you");
  // The You page's own button (on desktop the sidebar has one too).
  await page.getByRole("main").getByRole("button", { name: "Sign out" }).click();
  await expect(page.getByRole("button", { name: "Continue with Google" }).first()).toBeVisible();

  await page.reload();
  await expect(page.getByRole("button", { name: "Continue with Google" }).first()).toBeVisible();
});

test("the API rejects a request without a token, even with a session in the browser", async ({
  page,
}) => {
  await signIn(page, newUser("Cara"));
  const status = await page.evaluate(async () => (await fetch("/api/v1/me")).status);
  expect(status).toBe(401);
});
