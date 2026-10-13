import { expect, test, type Locator, type Page } from "@playwright/test";

import { newUser, signIn } from "./auth";
import { watchProblems } from "./problems";

async function addGuestTo(page: Page, slot: Locator, name: string): Promise<void> {
  await slot.click();
  await page.getByRole("dialog", { name: "Pick a player" }).getByRole("button", { name: "Add a guest" }).click();
  const guest = page.getByRole("dialog", { name: "Add a guest" });
  await guest.getByLabel("Guest's name").fill(name);
  await guest.getByRole("button", { name: "Add guest" }).click();
  await expect(guest).toBeHidden();
}

test("the members page: who's in, guests renamed or removed", async ({ page }) => {
  const nora = newUser("Nora");
  await signIn(page, nora);
  const problems = await watchProblems(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Start a group" }).first().click();
  await page.getByLabel("Group name").fill("Early Birds");
  await page.getByRole("button", { name: "Create group" }).click();
  await expect(page).toHaveURL(/\/groups\/[0-9a-f-]{36}$/);
  const groupUrl = page.url();

  // A singles game against guest Ivy, then a typo guest who never plays.
  await page.goto(`${groupUrl}/log`);
  await page.getByRole("button", { name: "Change rules" }).click();
  await page.getByText("Singles", { exact: true }).click();
  await page.getByRole("button", { name: "Done with rules" }).click();
  await addGuestTo(page, page.getByRole("button", { name: "Team B, player 1: pick a player" }), "Ivy");
  await page.getByLabel(`Game 1, ${nora.name}`).fill("11");
  await page.getByLabel("Game 1, Ivy").fill("6");
  await page.getByRole("button", { name: "Log game" }).click();
  await expect(page).toHaveURL(/\/play/);
  await page.getByRole("dialog", { name: "How did it go?" }).getByRole("button", { name: "Skip this game" }).click();
  await page.goto(`${groupUrl}/log`);
  await addGuestTo(page, page.getByRole("button", { name: "Team B, player 1: pick a player" }), "Ivvy");

  // The group page links to the members page.
  await page.goto(groupUrl);
  await page.getByRole("link", { name: /Members · 1/ }).click();
  await expect(page).toHaveURL(`${groupUrl}/members`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Members");
  const members = page.getByRole("region", { name: /Members · 1/ });
  await expect(members).toContainText("Played today");

  const guests = page.getByRole("region", { name: /Guests · 2/ });
  await expect(guests.getByRole("listitem").filter({ hasText: "Ivvy" })).toContainText("Guest · 0 games");
  await expect(guests.getByRole("listitem").filter({ hasText: "Ivy" }).first()).toBeVisible();

  // The typo goes.
  await page.getByRole("button", { name: "Edit Ivvy" }).click();
  const typo = page.getByRole("dialog", { name: "Ivvy" });
  await typo.getByRole("button", { name: "Remove guest" }).click();
  await expect(typo).toBeHidden();
  await expect(page.getByRole("region", { name: /Guests · 1/ })).not.toContainText("Ivvy");

  // Ivy has a game, so stays, but can be renamed.
  await page.getByRole("button", { name: "Edit Ivy" }).click();
  const ivy = page.getByRole("dialog", { name: "Ivy" });
  await expect(ivy.getByRole("button", { name: "Remove guest" })).toHaveCount(0);
  await expect(ivy).toContainText("is in games, so they stay");
  await ivy.getByLabel("Name").fill("Ivy Rose");
  await ivy.getByRole("button", { name: "Save name" }).click();
  await expect(ivy).toBeHidden();
  await expect(page.getByRole("region", { name: /Guests · 1/ })).toContainText("Ivy Rose");
  await expect(page.getByRole("region", { name: /Guests · 1/ })).toContainText("Guest · 1 game");

  expect(problems).toEqual([]);
});
