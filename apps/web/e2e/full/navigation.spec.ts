import { expect, test, type Page } from "@playwright/test";

import { newUser, signIn } from "./auth";
import { watchProblems } from "./problems";

function nav(page: Page) {
  // One of the two navs (sidebar or tab bar) is hidden at any width; this finds the visible one.
  return page.getByRole("navigation", { name: "Main" });
}

async function startGroup(page: Page, name: string): Promise<void> {
  await page.goto("/");
  await page.getByRole("button", { name: "Start a group" }).first().click();
  await page.getByLabel("Group name").fill(name);
  await page.getByRole("button", { name: "Create group" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(name);
}

test("the tabs move between pages and show where you are", async ({ page }) => {
  const user = newUser("Nia");
  await signIn(page, user);
  const problems = await watchProblems(page);
  await page.goto("/");

  for (const [label, path, heading] of [
    ["Games", "/games", "Games"],
    ["Board", "/board", "Leaderboard"],
    ["You", "/you", user.name],
    ["Home", "/", /^Good (morning|afternoon|evening), Nia\.$/],
  ] as const) {
    await nav(page).getByRole("link", { name: label }).click();
    await expect(page).toHaveURL(new RegExp(`${path}$`));
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(heading);
    await expect(nav(page).getByRole("link", { name: label })).toHaveAttribute("aria-current", "page");
  }
  expect(problems).toEqual([]);
});

test("Games and Board follow the chosen group and remember it", async ({ page }) => {
  await signIn(page, newUser("Omar"));
  await startGroup(page, "Alpha Crew");
  await startGroup(page, "Beta Crew");

  await page.goto("/games");
  const group = page.getByLabel("Group");
  await expect(group).toHaveValue(/.+/);
  await group.selectOption({ label: "Beta Crew" });
  await expect(page.getByRole("heading", { name: "No games in Beta Crew yet" })).toBeVisible();

  // Remembered across pages and reloads on this device.
  await page.goto("/board");
  await expect(page.getByLabel("Group")).toHaveValue(
    await page.getByLabel("Group").locator("option", { hasText: "Beta Crew" }).getAttribute("value") ?? "",
  );
  await page.reload();
  await expect(page.getByLabel("Group").locator("option:checked")).toHaveText("Beta Crew");
});

test("the board lists the crew, unranked, until games are confirmed", async ({ page }) => {
  const user = newUser("Pia");
  await signIn(page, user);
  await page.goto("/board");
  await expect(page.getByText("You're not in a group yet.", { exact: false })).toBeVisible();

  await startGroup(page, "Pia's Crew");
  await page.goto("/board");
  const roster = page.getByRole("list", { name: "Players, not yet ranked" });
  await expect(roster.getByRole("listitem")).toHaveCount(1);
  await expect(roster).toContainText(`${user.name} (you)`);
  await expect(roster).toContainText("Unrated");
});

test("appearance is remembered and applied before the page paints", async ({ page }) => {
  await signIn(page, newUser("Quinn"));
  const problems = await watchProblems(page);
  await page.goto("/you");
  const theme = () => page.evaluate(() => document.documentElement.dataset.theme ?? "system");

  await page.getByText("Dark", { exact: true }).click();
  expect(await theme()).toBe("dark");

  // After a reload, the inline script (carrying the CSP nonce) sets it before any app code.
  await page.reload({ waitUntil: "commit" });
  await page.waitForFunction(() => document.documentElement.dataset.theme !== undefined);
  expect(await theme()).toBe("dark");
  await expect(page.getByRole("radio", { name: "Dark" })).toBeChecked();

  await page.getByText("Match device", { exact: true }).click();
  expect(await theme()).toBe("system");
  await page.reload();
  await expect(page.getByRole("radio", { name: "Match device" })).toBeChecked();
  expect(await theme()).toBe("system");
  expect(problems).toEqual([]);
});
