import { expect, test } from "@playwright/test";

import { newUser, signIn, type TestUser } from "./auth";
import { watchProblems } from "./problems";

// dev/run.sh makes this address the admin.
const ADMIN: TestUser = { name: "Admin Test", email: "admin@popshot.test" };

test("the admin page is 'not found' for everyone else", async ({ page }) => {
  await signIn(page, newUser("Casey"));
  await page.goto("/admin");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("That page is out of bounds.");
  await expect(page.getByText("Right now")).toHaveCount(0);
});

test("the admin sees app-wide numbers and every crew", async ({ page }) => {
  const problems = await watchProblems(page);
  // Someone starts a crew...
  await signIn(page, newUser("Rio"));
  const crew = `Admin check ${String(Date.now())}`;
  await page.goto("/");
  await page.getByRole("button", { name: "Start a group" }).first().click();
  await page.getByLabel("Group name").fill(crew);
  await page.getByRole("button", { name: "Create group" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(crew);

  // ...and the admin sees it, with counts but no people.
  await signIn(page, ADMIN);
  await page.goto("/admin");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Admin");
  const now = page.getByRole("region", { name: "Right now" });
  await expect(now.getByText("People", { exact: true })).toBeVisible();
  await expect(page.getByRole("table", { name: "Each week, newest first" }).getByRole("row")).toHaveCount(13);
  await expect(page.getByRole("table", { name: "Coming back, by signup week" })).toBeVisible();
  const row = page
    .getByRole("list", { name: "Crews, most recently active first" })
    .getByRole("listitem")
    .filter({ hasText: crew });
  await expect(row).toContainText("1 member · no games yet · started");
  await expect(page.getByText("Rio Test")).toHaveCount(0);
  expect(problems).toEqual([]);
});

test("an old sign-in is asked to sign in again", async ({ page }) => {
  await signIn(page, ADMIN);
  // The emulator always signs in "now", so stand in for the API's answer to an old sign-in.
  await page.route("**/api/v1/admin/**", (route) =>
    route.fulfill({
      status: 403,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Sign in again to open the admin page." }),
    }),
  );
  await page.goto("/admin");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Sign in again");
  await expect(page.getByRole("button", { name: "Sign in with Google" })).toBeVisible();
});
