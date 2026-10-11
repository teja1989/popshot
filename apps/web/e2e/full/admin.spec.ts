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

test("the admin finds a person, opens them and their crew", async ({ page }) => {
  const problems = await watchProblems(page);
  const rio = newUser("Rio");
  await signIn(page, rio);
  const crew = `Lookup check ${String(Date.now())}`;
  await page.goto("/");
  await page.getByRole("button", { name: "Start a group" }).first().click();
  await page.getByLabel("Group name").fill(crew);
  await page.getByRole("button", { name: "Create group" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(crew);

  await signIn(page, ADMIN);
  await page.goto("/admin");
  const search = page.getByRole("search");
  // Emails come from Firebase, which isn't reachable locally: it says so.
  await search.getByLabel("Name, email or id").fill(rio.email);
  await search.getByRole("button", { name: "Find" }).click();
  await expect(page.getByText("Email search isn't available here. Try a name.")).toBeVisible();

  // e2e users are named "<First> Test"; the crew name picks out this run's Rio.
  await search.getByLabel("Name, email or id").fill("Rio Test");
  await search.getByRole("button", { name: "Find" }).click();
  const found = page.getByRole("list", { name: "People found" });
  await expect(found.getByRole("link").first()).toBeVisible();

  // Open the crew from the crews list, then Rio from the crew.
  await page.getByRole("list", { name: "Crews, most recently active first" }).getByRole("link", { name: crew }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(crew);
  const people = page.getByRole("list", { name: "People in this crew" });
  await expect(people).toContainText("Lead · 0 games · joined");
  await expect(people).toContainText("started the crew");
  await people.getByRole("link", { name: /Rio Test/ }).click();

  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Rio Test");
  await expect(page.getByText("Email unavailable here")).toBeVisible();
  const crews = page.getByRole("list", { name: "Their crews" });
  await expect(crews.getByRole("link", { name: crew })).toBeVisible();
  await expect(crews).toContainText("Lead · 0 games");
  await page.getByRole("link", { name: "← Admin" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Admin");
  expect(problems).toEqual([]);
});
