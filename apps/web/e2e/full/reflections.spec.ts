import { expect, test, type Page } from "@playwright/test";

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

/** Log a singles game against the guest Gary (added the first time). Lands on Games. */
async function logSingles(page: Page, groupUrl: string, firstTime: boolean): Promise<void> {
  await page.goto(`${groupUrl}/log`);
  await page.getByText("Singles", { exact: true }).click();
  await page.getByRole("button", { name: "Team B, player 1: pick a player" }).click();
  const picker = page.getByRole("dialog", { name: "Pick a player" });
  if (firstTime) {
    await picker.getByPlaceholder("Their name").fill("Gary");
    await picker.getByRole("button", { name: "Add guest" }).click();
  } else {
    await picker.getByRole("button", { name: /^Gary/ }).click();
  }
  await expect(picker).toBeHidden();
  await page.getByRole("textbox", { name: /^Game 1,/ }).first().fill("11");
  await page.getByRole("textbox", { name: "Game 1, Gary" }).fill("4");
  await page.getByRole("button", { name: "Log game" }).click();
  await expect(page).toHaveURL(/\/games$/);
}

test("reflect after a game, skip one, and keep it to yourself", async ({ page }) => {
  await signIn(page, newUser("Casey"));
  const problems = await watchProblems(page);
  const groupUrl = await startGroup(page, "Reflection Crew");

  await logSingles(page, groupUrl, true);
  // You played, so "How did it go?" opens straight away. It's optional.
  const sheet = page.getByRole("dialog", { name: "How did it go?" });
  await expect(sheet).toBeVisible();
  await expect(sheet).toContainText("nobody else sees this");
  const wentWell = sheet.getByRole("group", { name: /What went well/ });
  const toImprove = sheet.getByRole("group", { name: /What to improve/ });
  await expect(sheet.getByRole("button", { name: "Save" })).toBeDisabled();
  await wentWell.getByRole("button", { name: "Footwork" }).click();
  await expect(wentWell.getByRole("button", { name: /Footwork/ })).toHaveAttribute("aria-pressed", "true");
  // The same option can't also go under what to improve.
  await expect(toImprove.getByRole("button", { name: /Footwork/ })).toBeDisabled();
  // At most six.
  for (const name of ["Return of serve", "Third-shot drops", "Poaching", "Backhand consistency", "Court coverage"]) {
    await wentWell.getByRole("button", { name }).click();
  }
  await expect(wentWell.getByRole("button", { name: "Lobs and overheads" })).toBeDisabled();
  for (const name of ["Poaching", "Backhand consistency", "Court coverage"]) {
    await wentWell.getByRole("button", { name }).click();
  }
  await toImprove.getByRole("button", { name: "Serve consistency" }).click();
  await sheet.getByRole("button", { name: "Save" }).click();
  await expect(sheet).toBeHidden();
  const first = page.getByRole("listitem").filter({ hasText: "Went well:" });
  await expect(first).toContainText("Went well: Footwork, Return of serve, Third-shot drops. To improve: Serve consistency.");

  // Closing the sheet keeps the prompt on the card; skipping clears it.
  await logSingles(page, groupUrl, false);
  await expect(sheet).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  await page.getByRole("button", { name: /How did it go for you\?/ }).click();
  await sheet.getByRole("button", { name: "Skip this game" }).click();
  await expect(sheet).toBeHidden();
  await expect(page.getByRole("button", { name: /How did it go for you\?/ })).toHaveCount(0);
  await expect(page.getByText("No notes for this game.")).toBeVisible();
  expect(problems).toEqual([]);
});

test("pick strengths and areas, and promote a repeated reflection", async ({ page }) => {
  await signIn(page, newUser("Sam"));
  const problems = await watchProblems(page);
  const groupUrl = await startGroup(page, "Profile Crew");

  await page.goto("/you");
  const section = page.getByRole("region", { name: "Your game" });
  await expect(section).toContainText("Only you can see this");
  await section.getByRole("button", { name: "Edit your game" }).click();
  const edit = page.getByRole("dialog", { name: "Your game" });
  const strengths = edit.getByRole("group", { name: /Strengths/ });
  for (const name of ["Footwork", "Court coverage", "Serve consistency", "Return of serve", "Poaching", "Backhand consistency"]) {
    await strengths.getByRole("button", { name }).click();
  }
  await expect(strengths.getByRole("button", { name: "Lobs and overheads" })).toBeDisabled();
  for (const name of ["Poaching", "Backhand consistency"]) {
    await strengths.getByRole("button", { name }).click();
  }
  await expect(edit.getByRole("group", { name: /Areas to improve/ }).getByRole("button", { name: /Footwork/ })).toBeDisabled();
  await strengths.getByRole("button", { name: /Return of serve/ }).click();
  await edit.getByRole("group", { name: /Areas to improve/ }).getByRole("button", { name: "Dinking patience" }).click();
  await edit.getByRole("button", { name: "Save" }).click();
  await expect(edit).toBeHidden();
  await expect(section).toContainText("Footwork");
  await expect(section).toContainText("Dinking patience");

  // Five games where third-shot drops went well: a suggestion appears.
  for (let n = 0; n < 5; n++) {
    await logSingles(page, groupUrl, n === 0);
    const sheet = page.getByRole("dialog", { name: "How did it go?" });
    if (n === 0) {
      // Profile items are marked, not pre-picked.
      await expect(sheet.getByRole("button", { name: /Footwork · in your profile/ })).toHaveAttribute("aria-pressed", "false");
    }
    await sheet.getByRole("group", { name: /What went well/ }).getByRole("button", { name: "Third-shot drops" }).click();
    await sheet.getByRole("button", { name: "Save" }).click();
    await expect(sheet).toBeHidden();
  }
  await page.goto("/you");
  await expect(section).toContainText("You picked Third-shot drops as going well in 5 of your last 5 games.");
  await section.getByRole("button", { name: "Add to Strengths" }).click();
  await expect(section).not.toContainText("You picked Third-shot drops");
  await expect(section.getByRole("list").first()).toContainText("Third-shot drops");
  expect(problems).toEqual([]);
});
