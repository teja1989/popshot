import { expect, test, type Page } from "@playwright/test";

import { newUser, signIn } from "./auth";
import { watchProblems } from "./problems";

function nav(page: Page) {
  // One of the two navs (sidebar or tab bar) is hidden at any width; this finds the visible one.
  return page.getByRole("navigation", { name: "Main" });
}

async function startGroup(page: Page, name: string): Promise<string> {
  await page.goto("/");
  await page.getByRole("button", { name: "Start a group" }).first().click();
  await page.getByLabel("Group name").fill(name);
  await page.getByRole("button", { name: "Create group" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(name);
  return page.url();
}

test("the tabs move between pages and show where you are", async ({ page }) => {
  const user = newUser("Nia");
  await signIn(page, user);
  const problems = await watchProblems(page);
  await page.goto("/");

  for (const [label, path, heading] of [
    ["Games", "/games", "Games"],
    ["Board", "/board", "Board"],
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

test("the board shows crew points from the first game", async ({ page }) => {
  const user = newUser("Pia");
  await signIn(page, user);
  const problems = await watchProblems(page);
  await page.goto("/board");
  await expect(page.getByText("You're not in a group yet.", { exact: false })).toBeVisible();

  const groupUrl = await startGroup(page, "Pia's Crew");
  await page.goto("/board");
  await expect(page.getByRole("heading", { name: "Nobody's ranked yet" })).toBeVisible();
  const starting = page.getByRole("list", { name: /Getting started/ });
  await expect(starting).toContainText(`${user.name} (you)`);
  await expect(starting).toContainText("0 of 10 games");

  // One win against a guest: crew points move above the 3.00 start, still getting started.
  await page.goto(`${groupUrl}/log`);
  await page.getByText("Singles", { exact: true }).click();
  await page.getByRole("button", { name: "Team B, player 1: pick a player" }).click();
  await page.getByRole("dialog", { name: "Pick a player" }).getByRole("button", { name: "Add a guest" }).click();
  await page.getByRole("dialog", { name: "Add a guest" }).getByLabel("Guest's name").fill("Lou");
  await page.getByRole("dialog", { name: "Add a guest" }).getByRole("button", { name: "Add guest" }).click();
  await page.getByLabel(`Game 1, ${user.name}`).fill("11");
  await page.getByLabel("Game 1, Lou").fill("3");
  await page.getByRole("button", { name: "Log game" }).click();
  await expect(page).toHaveURL(/\/games$/);

  await page.goto("/board");
  const mine = starting.getByRole("listitem").filter({ hasText: user.name });
  await expect(mine).toContainText("1 of 10 games");
  const points = Number(await mine.getByText(/^\d\.\d\d$/).textContent());
  expect(points).toBeGreaterThan(3);
  expect(points).toBeLessThanOrEqual(6);
  await expect(starting.getByRole("listitem").filter({ hasText: "Lou" })).toContainText("guest");
  expect(problems).toEqual([]);
});

test("the ⓘ explains crew points and how they differ from your level", async ({ page }) => {
  await signIn(page, newUser("Ines"));
  const problems = await watchProblems(page);
  await startGroup(page, "Ines's Crew");
  for (const path of ["/board", "/you"]) {
    await page.goto(path);
    await page.getByRole("button", { name: "How crew points work" }).first().click();
    const sheet = page.getByRole("dialog", { name: "How crew points work" });
    await expect(sheet).toContainText("Your level vs. your crew points");
    await expect(sheet).toContainText("only where your crew points start");
    await expect(sheet).toContainText("+0.03");
    await expect(sheet).toContainText("Advanced · 4.00");
    await page.keyboard.press("Escape");
    await expect(sheet).toBeHidden();
  }
  expect(problems).toEqual([]);
});

test("your level sets where crew points start", async ({ page }) => {
  await signIn(page, newUser("Kai"));
  await page.goto("/you");
  const section = page.getByRole("region", { name: "Crew points" });
  await expect(section).toContainText("Your crew points show up after your first game.");
  await expect(section.getByRole("radio", { name: /Not set/ })).toBeChecked();
  await section.getByRole("radio", { name: /Advanced/ }).check();
  await page.reload();
  await expect(page.getByRole("region", { name: "Crew points" }).getByRole("radio", { name: /Advanced/ })).toBeChecked();
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
