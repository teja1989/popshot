import { expect, test, type Page } from "@playwright/test";

import { newUser, signIn } from "./auth";
import { watchProblems } from "./problems";

function nav(page: Page) {
  // One of the two navs (sidebar or tab bar) is hidden at any width; this finds the visible one.
  return page.getByRole("navigation", { name: "Main" });
}

async function startCrew(page: Page, name: string) {
  await page.goto("/");
  await page.getByRole("button", { name: "Start a group" }).first().click();
  await page.getByLabel("Group name").fill(name);
  await page.getByRole("button", { name: "Create group" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(name);
}

test("More lists only what works: no crew, no crew items", async ({ page }) => {
  const problems = await watchProblems(page);
  await signIn(page, newUser("Oli"));
  await page.goto("/");
  await nav(page).getByRole("link", { name: "More" }).click();
  await expect(page).toHaveURL(/\/more$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("More");
  await expect(nav(page).getByRole("link", { name: "More" })).toHaveAttribute("aria-current", "page");

  await expect(page.getByRole("region", { name: "You" }).getByRole("link", { name: /Your stats/ })).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Popshot" }).getByRole("button", { name: /Start a crew/ }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: /Log a game/ })).toHaveCount(0);
  await expect(page.getByRole("region", { name: /Your crew/ })).toHaveCount(0);
  expect(problems).toEqual([]);
});

test("More opens crew pages and jumps to sections, and search narrows the list", async ({ page }) => {
  const problems = await watchProblems(page);
  const user = newUser("Pia");
  await signIn(page, user);
  const crew = `More check ${String(Date.now())}`;
  await startCrew(page, crew);

  await page.goto("/more");
  await expect(page.getByRole("region", { name: `Your crew · ${crew}` })).toBeVisible();
  // Events stay hidden: the switch isn't on for this crew.
  await expect(page.getByRole("link", { name: /^Events/ })).toHaveCount(0);

  const search = page.getByRole("searchbox", { name: "Search" });
  await search.fill("invite");
  await expect(page.getByRole("status").filter({ hasText: "matches" })).toHaveText("3 matches");
  await expect(page.getByRole("link", { name: /Members and invites/ })).toBeVisible();
  await expect(page.getByRole("link", { name: /Your stats/ })).toHaveCount(0);
  await search.fill("xylophone");
  await expect(page.getByText("Nothing matches “xylophone”.", { exact: false })).toBeVisible();
  await search.fill("");

  await page.getByRole("link", { name: /Members and invites/ }).click();
  await expect(page).toHaveURL(/\/groups\/[0-9a-f-]+\/members$/);

  // A section further down a page: it waits for the page to load, then lands there.
  await page.goto("/more");
  await page.getByRole("link", { name: /Focus areas/ }).click();
  await expect(page).toHaveURL(/\/you#focus-heading$/);
  await expect(page.getByRole("heading", { name: "Your game", level: 2 })).toBeFocused();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(user.name);
  expect(problems).toEqual([]);
});

test("Join with an invite link opens from More", async ({ page }) => {
  await signIn(page, newUser("Rae"));
  await page.goto("/more");
  await page.getByRole("button", { name: /Join with an invite link/ }).click();
  await expect(page.getByRole("dialog")).toBeVisible();
});
