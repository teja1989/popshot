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
  await page.getByRole("dialog", { name: "Pick a player" }).getByRole("button", { name: "Add a guest" }).click();
  const guest = page.getByRole("dialog", { name: "Add a guest" });
  await guest.getByLabel("Guest's name").fill(name);
  await guest.getByRole("button", { name: "Add guest" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
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
  await picker.getByRole("button", { name: "Add a guest" }).click();
  const guest = page.getByRole("dialog", { name: "Add a guest" });
  await guest.getByLabel("Guest's name").fill("gary");
  await guest.getByRole("button", { name: "Add guest" }).click();
  await expect(guest.getByRole("alert")).toContainText("already a player called gary");
  await page.keyboard.press("Escape");

  // A score that can't happen is explained as you type.
  await page.getByLabel(`Game 1, ${casey.name} & Gary`).fill("11");
  await page.getByLabel("Game 1, Jo & Robin").fill("10");
  await expect(page.getByText("Past game point, the winner finishes exactly two points ahead.")).toBeVisible();
  await page.getByLabel(`Game 1, ${casey.name} & Gary`).fill("12");
  await expect(page.getByText(`✓ ${casey.name} & Gary win 12–10.`)).toBeVisible();

  await page.getByRole("button", { name: "Log game" }).click();
  await expect(page).toHaveURL(/\/games$/);
  // You played, so the optional reflection opens; close it without answering.
  await expect(page.getByRole("dialog", { name: "How did it go?" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("status")).toContainText("Game logged.");
  const card = page.getByRole("listitem").filter({ hasText: "Jo & Robin" });
  // It counts straight away: no confirmation step.
  await expect(card).not.toContainText("Waiting");
  await expect(card).toContainText("Logged by you");
  await expect(card.getByRole("table")).toContainText(`${casey.name} & Gary`);

  // The scorer can fix it: the same form, filled in.
  await card.getByRole("link", { name: "Edit game" }).click();
  await expect(page.getByRole("heading", { name: "Edit game" })).toBeVisible();
  await expect(page.getByLabel(`Game 1, ${casey.name} & Gary`)).toHaveValue("12");
  await expect(page.getByLabel("Game 1, Jo & Robin")).toHaveValue("10");
  await page.getByLabel(`Game 1, ${casey.name} & Gary`).fill("6");
  await page.getByLabel("Game 1, Jo & Robin").fill("11");
  await expect(page.getByText("✓ Jo & Robin win 11–6.")).toBeVisible();
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page).toHaveURL(/\/games$/);
  await expect(card.getByRole("cell")).toHaveText(["6", "11"]);

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

  // The rules start as one line, from the crew's usual ones.
  const rules = page.getByRole("region", { name: "Rules" });
  await expect(rules).toContainText("Doubles · 1 game · to 11, win by 2");
  await expect(page.getByText("Best of 3", { exact: true })).toBeHidden();
  await page.getByRole("button", { name: "Change rules" }).click();
  await page.getByText("Singles", { exact: true }).click();
  await page.getByText("Best of 3", { exact: true }).click();
  await page.getByRole("button", { name: "Done with rules" }).click();
  await expect(rules).toContainText("Singles · best of 3 · to 11, win by 2");
  await expect(page.getByText("Best of 3", { exact: true })).toBeHidden();
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
  await page.getByRole("dialog", { name: "How did it go?" }).getByRole("button", { name: "Skip this game" }).click();
  const card = page.getByRole("listitem").filter({ hasText: "Alex" });
  await expect(card).toContainText("Singles · to 11");
  await expect(card.getByRole("cell")).toHaveCount(6);
});

test("a best of 5 adds game rows only while the match is still open", async ({ page }) => {
  const kai = newUser("Kai");
  await signIn(page, kai);
  const groupUrl = await startGroup(page, "Long Matches");
  await page.goto(`${groupUrl}/log`);

  await page.getByRole("button", { name: "Change rules" }).click();
  await page.getByText("Singles", { exact: true }).click();
  await page.getByText("Best of 5", { exact: true }).click();
  await addGuestTo(page, page.getByRole("button", { name: "Team B, player 1: pick a player" }), "Lee");

  // Three rows to start: the fewest that could decide it.
  await expect(page.getByLabel(/^Game \d, Lee$/)).toHaveCount(3);
  const scores: [string, string][] = [
    ["11", "7"],
    ["9", "11"],
    ["11", "9"],
    ["5", "11"],
  ];
  for (const [index, [mine, theirs]] of scores.entries()) {
    await page.getByLabel(`Game ${String(index + 1)}, ${kai.name}`).fill(mine);
    await page.getByLabel(`Game ${String(index + 1)}, Lee`).fill(theirs);
  }
  // 2–2: the fifth game appears, and logging waits for it.
  await expect(page.getByLabel(/^Game \d, Lee$/)).toHaveCount(5);
  await expect(page.getByText(/^✓/)).toHaveCount(0);
  await page.getByLabel(`Game 5, ${kai.name}`).fill("12");
  await page.getByLabel("Game 5, Lee").fill("10");
  await expect(page.getByText(`✓ ${kai.name} wins 11–7, 9–11, 11–9, 5–11, 12–10.`)).toBeVisible();

  await page.getByRole("button", { name: "Log game" }).click();
  await expect(page).toHaveURL(/\/games$/);
  await page.getByRole("dialog", { name: "How did it go?" }).getByRole("button", { name: "Skip this game" }).click();
  const card = page.getByRole("listitem").filter({ hasText: "Lee" });
  await expect(card.getByRole("cell")).toHaveCount(10);
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

test("the player picker works at keyboard height on a phone", async ({ page }) => {
  // Roughly what's left of a phone screen with the on-screen keyboard up.
  await page.setViewportSize({ width: 390, height: 420 });
  await signIn(page, newUser("Kim"));
  const problems = await watchProblems(page);
  const groupUrl = await startGroup(page, "Small Screen");
  await page.goto(`${groupUrl}/log`);

  await page.getByRole("button", { name: "Team B, player 1: pick a player" }).click();
  const picker = page.getByRole("dialog", { name: "Pick a player" });
  await expect(picker).toBeVisible();
  // Opening the picker doesn't focus a text field, so no keyboard pops up over the list.
  expect(await page.evaluate(() => document.activeElement?.tagName)).not.toBe("INPUT");

  // Searching for someone who isn't there offers to add them, name filled in.
  await picker.getByLabel("Find a player").fill("Mo");
  await picker.getByRole("button", { name: "Add “Mo” as a guest" }).click();
  const guest = page.getByRole("dialog", { name: "Add a guest" });
  const field = guest.getByLabel("Guest's name");
  await expect(field).toBeFocused();
  await expect(field).toHaveValue("Mo");
  // The field and its button sit at the top, inside what's visible.
  await expect(field).toBeInViewport();
  await expect(guest.getByRole("button", { name: "Add guest" })).toBeInViewport();
  await field.fill("Morgan");
  await guest.getByRole("button", { name: "Add guest" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(page.getByRole("button", { name: "Team B, player 1: Morgan. Change" })).toBeVisible();
  expect(problems).toEqual([]);
});

test("home counts the games you've played, and the logo goes home", async ({ page }) => {
  await signIn(page, newUser("Lee"));
  const groupUrl = await startGroup(page, "Count Crew");
  await page.goto("/");
  const stats = page.getByRole("definition").filter({ hasText: /^\d/ });
  await expect(page.getByText("Games played")).toBeVisible();
  await expect(stats.nth(1)).toHaveText("0");

  await page.goto(`${groupUrl}/log`);
  await page.getByRole("button", { name: "Change rules" }).click();
  await page.getByText("Singles", { exact: true }).click();
  await addGuestTo(page, page.getByRole("button", { name: "Team B, player 1: pick a player" }), "Pat");
  await page
    .getByRole("textbox", { name: /^Game 1,/ })
    .first()
    .fill("11");
  await page.getByRole("textbox", { name: "Game 1, Pat" }).fill("6");
  await page.getByRole("button", { name: "Log game" }).click();
  await expect(page).toHaveURL(/\/games$/);
  await page.getByRole("dialog", { name: "How did it go?" }).getByRole("button", { name: "Skip this game" }).click();

  // The logo is a link home from anywhere in the app.
  await page.getByRole("link", { name: "Popshot home" }).first().click();
  await expect(page).toHaveURL(/\/$/);
  await expect(stats.nth(1)).toHaveText("1");
  await expect(page.getByRole("link", { name: /Count Crew/ })).toContainText("1 game");
});

test("other players see a logged game straight away, but only the scorer can edit it", async ({ page, browser }) => {
  const casey = newUser("Casey");
  const sam = newUser("Sam");
  await signIn(page, casey);
  const groupUrl = await startGroup(page, "Open Book");

  // Sam joins through an invite link, and Casey lets Sam in.
  await page.getByRole("button", { name: "Make an invite link" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Make link" }).click();
  const link = await page.getByRole("dialog", { name: "Your invite link" }).getByLabel("Link").inputValue();
  await page.keyboard.press("Escape");
  const other = await browser.newPage();
  await signIn(other, sam);
  await other.goto(link);
  await other.getByRole("button", { name: "Ask to join" }).click();
  await expect(other.getByRole("heading", { name: "Waiting for approval" })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: `Let ${sam.name} in` }).click();
  await expect(page.getByRole("region", { name: /Members · 2/ })).toBeVisible();

  // Casey logs a singles game against Sam.
  await page.goto(`${groupUrl}/log`);
  await page.getByRole("button", { name: "Change rules" }).click();
  await page.getByText("Singles", { exact: true }).click();
  await page.getByRole("button", { name: "Team B, player 1: pick a player" }).click();
  await page
    .getByRole("dialog", { name: "Pick a player" })
    .getByRole("button", { name: new RegExp(sam.name) })
    .click();
  await page.getByLabel(`Game 1, ${casey.name}`).fill("11");
  await page.getByLabel(`Game 1, ${sam.name}`).fill("8");
  await page.getByRole("button", { name: "Log game" }).click();
  await expect(page).toHaveURL(/\/games$/);
  const sheet = page.getByRole("dialog", { name: "How did it go?" });
  await expect(sheet).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  const gameUrl = await page.getByRole("link", { name: "Edit game" }).getAttribute("href");

  // Sam sees it right away, with Casey as the scorer, and no Edit.
  await other.goto("/games");
  const card = other.getByRole("listitem").filter({ hasText: casey.name });
  await expect(card).toContainText(`Logged by ${casey.name}`);
  await expect(card.getByRole("cell")).toHaveText(["11", "8"]);
  await expect(card.getByRole("link", { name: "Edit game" })).toHaveCount(0);
  await expect(card.getByRole("button", { name: "Delete" })).toHaveCount(0);
  // Sam played, so the optional "How did it go?" is offered here too.
  await expect(card.getByRole("button", { name: /How did it go for you\?/ })).toBeVisible();
  // Going to the edit page directly says no.
  await other.goto(gameUrl ?? "/");
  await expect(other.getByText("Only the person who logged this game can edit it.")).toBeVisible();
  await other.close();
});
