import { expect, test, type Locator, type Page } from "@playwright/test";

import { newUser, signIn } from "./auth";
import { watchProblems } from "./problems";

async function startGroup(page: Page, name: string): Promise<string> {
  await page.goto("/");
  await page.getByRole("button", { name: "Start a group" }).first().click();
  const dialog = page.getByRole("dialog", { name: "Start a group" });
  await dialog.getByLabel("Group name").fill(name);
  await dialog.getByRole("button", { name: "Create group" }).click();
  await expect(page).toHaveURL(/\/groups\/[0-9a-f-]{36}$/);
  return page.url();
}

async function addGuestTo(page: Page, slot: Locator, name: string): Promise<void> {
  await slot.click();
  const picker = page.getByRole("dialog", { name: "Pick a player" });
  await picker.getByPlaceholder("Their name").fill(name);
  await picker.getByRole("button", { name: "Add guest" }).click();
  await expect(picker).toBeHidden();
}

test("log a doubles game with guests, see it, and delete it", async ({ page }) => {
  const casey = newUser("Casey");
  await signIn(page, casey);
  const problems = await watchProblems(page);
  await startGroup(page, "Thursday Smashers");

  await page.getByRole("link", { name: "Log a game" }).click();
  await expect(page.getByRole("heading", { name: "Log a game" })).toBeVisible();
  // You start on team A.
  await expect(page.getByRole("button", { name: `Team A, player 1: ${casey.name}. Change` })).toBeVisible();

  await addGuestTo(page, page.getByRole("button", { name: "Team A, player 2: pick a player" }), "Gary");
  // Adding a guest doesn't also submit the log form around the picker.
  await expect(page.getByText("Pick two players for each team.")).toHaveCount(0);
  await addGuestTo(page, page.getByRole("button", { name: "Team B, player 1: pick a player" }), "Jo");
  await addGuestTo(page, page.getByRole("button", { name: "Team B, player 2: pick a player" }), "Robin");

  // The same name can't be added twice, and picked players are marked.
  await page.getByRole("button", { name: "Team B, player 2: Robin. Change" }).click();
  const picker = page.getByRole("dialog", { name: "Pick a player" });
  await expect(picker.getByRole("button", { name: /Gary/ })).toBeDisabled();
  await picker.getByPlaceholder("Their name").fill("gary");
  await picker.getByRole("button", { name: "Add guest" }).click();
  await expect(picker.getByRole("alert")).toContainText("already a player called gary");
  await page.keyboard.press("Escape");

  // A score that can't happen is explained as you type.
  await page.getByLabel(`Game 1, ${casey.name} & Gary`).fill("11");
  await page.getByLabel("Game 1, Jo & Robin").fill("10");
  await expect(page.getByText("Past game point, the winner finishes exactly two points ahead.")).toBeVisible();
  await page.getByLabel(`Game 1, ${casey.name} & Gary`).fill("12");
  await expect(page.getByText(`✓ ${casey.name} & Gary win 12–10.`)).toBeVisible();

  await page.getByRole("button", { name: "Log game" }).click();
  await expect(page).toHaveURL(/\/games$/);
  await expect(page.getByRole("status")).toContainText("Game logged.");
  const card = page.getByRole("listitem").filter({ hasText: "Jo & Robin" });
  await expect(card).toContainText("Waiting for confirmation");
  await expect(card).toContainText("logged by you");
  await expect(card.getByRole("table")).toContainText(`${casey.name} & Gary`);

  await card.getByRole("button", { name: "Delete" }).click();
  await card.getByRole("button", { name: "Delete game" }).click();
  await expect(page.getByRole("heading", { name: "No games in Thursday Smashers yet" })).toBeVisible();
  // The only failed request is the duplicate guest, refused on purpose above.
  expect(problems.filter((p) => !p.includes("409"))).toEqual([]);
  expect(problems.filter((p) => p.includes("409"))).toHaveLength(2);
});

test("best of three shows a third game only when it's one each", async ({ page }) => {
  const sam = newUser("Sam");
  await signIn(page, sam);
  const groupUrl = await startGroup(page, "Singles Club");
  await page.goto(`${groupUrl}/log`);

  await page.getByText("Singles", { exact: true }).click();
  await page.getByText("Best of 3", { exact: true }).click();
  await addGuestTo(page, page.getByRole("button", { name: "Team B, player 1: pick a player" }), "Alex");

  await expect(page.getByLabel(/^Game 3,/)).toHaveCount(0);
  await page.getByLabel(`Game 1, ${sam.name}`).fill("11");
  await page.getByLabel("Game 1, Alex").fill("4");
  await page.getByLabel(`Game 2, ${sam.name}`).fill("6");
  await page.getByLabel("Game 2, Alex").fill("11");
  await expect(page.getByLabel(/^Game 3,/)).toHaveCount(2);
  await page.getByLabel(`Game 3, ${sam.name}`).fill("13");
  await page.getByLabel("Game 3, Alex").fill("11");
  await expect(page.getByText(`✓ ${sam.name} wins 11–4, 6–11, 13–11.`)).toBeVisible();

  // Logged earlier in the day.
  await page.getByText("Earlier", { exact: true }).click();
  await expect(page.getByLabel("Played at")).toBeVisible();
  await page.getByRole("button", { name: "Log game" }).click();
  await expect(page).toHaveURL(/\/games$/);
  const card = page.getByRole("listitem").filter({ hasText: "Alex" });
  await expect(card).toContainText("Singles · to 11");
  await expect(card.getByRole("cell")).toHaveCount(6);
});

test("you can't log a game until both teams are picked", async ({ page }) => {
  await signIn(page, newUser("Robin"));
  const groupUrl = await startGroup(page, "Early Birds");
  await page.goto(`${groupUrl}/log`);
  await page.getByRole("button", { name: "Log game" }).click();
  await expect(page.getByText("Pick two players for each team.")).toBeVisible();
  await expect(page).toHaveURL(/\/log$/);
});

test("edit your name and see it across the app", async ({ page }) => {
  const jordan = newUser("Jordan");
  await signIn(page, jordan);
  const problems = await watchProblems(page);
  const groupUrl = await startGroup(page, "Name Game");

  await page.goto("/you");
  await page.getByRole("button", { name: "Edit name" }).click();
  const sheet = page.getByRole("dialog", { name: "Your name" });
  await expect(sheet.getByLabel("Name")).toHaveValue(jordan.name);
  await sheet.getByLabel("Name").fill("   ");
  await sheet.getByRole("button", { name: "Save name" }).click();
  await expect(sheet.getByRole("alert")).toHaveText("Your name can't be empty.");
  await sheet.getByLabel("Name").fill("JJ");
  await sheet.getByRole("button", { name: "Save name" }).click();
  await expect(sheet).toBeHidden();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("JJ");

  await page.goto(groupUrl);
  await expect(page.getByRole("region", { name: /Members/ })).toContainText("JJ (you)");
  // It survives a reload (and so a fresh sign-in, which never overwrites it).
  await page.reload();
  await expect(page.getByRole("region", { name: /Members/ })).toContainText("JJ (you)");
  expect(problems).toEqual([]);
});
