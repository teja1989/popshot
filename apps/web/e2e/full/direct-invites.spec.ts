import { expect, test, type Page } from "@playwright/test";

import { newUser, signIn } from "./auth";
import { toMembers } from "./members";
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

async function codeOf(page: Page): Promise<string> {
  await page.goto("/you/settings");
  const code = page.getByLabel("Your code");
  await expect(code).toHaveText(/^[0-9A-Z]{4}-[0-9A-Z]{4}$/);
  return (await code.textContent()) ?? "";
}

async function inviteByCode(page: Page, code: string, firstName: string): Promise<void> {
  await toMembers(page);
  await page.getByRole("button", { name: "Invite someone" }).click();
  const sheet = page.getByRole("dialog", { name: "Invite someone" });
  await sheet.getByLabel("Their code").fill(code.toLowerCase());
  await sheet.getByRole("button", { name: "Find" }).click();
  await sheet
    .getByRole("list", { name: "Found by code" })
    .getByRole("button", { name: `Invite ${firstName}` })
    .click();
  await expect(sheet.getByText(`Invite sent to ${firstName}.`)).toBeVisible();
  await sheet.getByRole("button", { name: "Close" }).click();
  await expect(sheet).toBeHidden();
}

test("a lead invites by code, and the person joins from Home", async ({ page, browser }) => {
  const casey = newUser("Casey");
  const robin = newUser("Robin");
  await signIn(page, casey);
  const problems = await watchProblems(page);
  const groupUrl = await startGroup(page, "Dawn Dinkers");

  const other = await browser.newPage();
  await signIn(other, robin);
  const otherProblems = await watchProblems(other);
  const code = await codeOf(other);

  await page.goto(groupUrl);
  await inviteByCode(page, code, "Robin");
  const waiting = page.getByRole("list", { name: "Waiting for an answer" });
  await expect(waiting).toContainText(robin.name);
  await expect(waiting).toContainText("Expires in 14 days");

  // Robin sees it on Home and joins.
  await other.goto("/");
  const invites = other.getByRole("region", { name: "Invites for you" });
  await expect(invites).toContainText("Dawn Dinkers");
  await expect(invites).toContainText(`${casey.name} invited you · 1 member`);
  await invites.getByRole("button", { name: "Join Dawn Dinkers" }).click();
  await expect(other).toHaveURL(groupUrl);
  await expect(other.getByRole("link", { name: /Members · 2/ })).toBeVisible();

  await page.reload();
  await expect(page.getByRole("region", { name: /Members · 2/ })).toContainText(robin.name);
  await expect(page.getByRole("list", { name: "Waiting for an answer" })).toHaveCount(0);

  // In Casey's next crew, Robin is someone Casey knows: found by name, no code needed.
  await startGroup(page, "Sunset Smash");
  await toMembers(page);
  await page.getByRole("button", { name: "Invite someone" }).click();
  const sheet = page.getByRole("dialog", { name: "Invite someone" });
  await sheet.getByLabel("Search by name").fill("rob");
  const known = sheet.getByRole("list", { name: "People you know" });
  await known.getByRole("button", { name: `Invite ${robin.name}` }).click();
  await expect(known).toContainText("Invited");

  expect(problems).toEqual([]);
  expect(otherProblems).toEqual([]);
});

test("saying no is quiet, and a crew can be stopped from inviting again", async ({ page, browser }) => {
  const casey = newUser("Casey");
  const jo = newUser("Jo");
  await signIn(page, casey);
  const groupUrl = await startGroup(page, "Lunch Dinkers");

  const other = await browser.newPage();
  await signIn(other, jo);
  const otherProblems = await watchProblems(other);
  const code = await codeOf(other);
  await page.goto(groupUrl);
  await inviteByCode(page, code, "Jo");

  await other.goto("/");
  const invites = other.getByRole("region", { name: "Invites for you" });
  await invites.getByRole("button", { name: "No thanks, and don't invite me again" }).click();
  await expect(other.getByText(/Lunch Dinkers can't invite you again/)).toBeVisible();
  await expect(other.getByRole("region", { name: "Invites for you" })).toHaveCount(0);

  // The lead just sees it gone.
  await page.reload();
  await expect(page.getByRole("list", { name: "Waiting for an answer" })).toHaveCount(0);

  // Jo can change their mind on the You page, and get a new code.
  await other.goto("/you/settings");
  const section = other.getByRole("region", { name: "Your Popshot code" });
  await expect(section).toContainText("Crews that can't invite you");
  await section.getByRole("button", { name: "Allow invites" }).click();
  await expect(section).toContainText("Lunch Dinkers can invite you again.");
  await section.getByRole("button", { name: "Get a new code" }).click();
  await expect(section).toContainText("New code made.");
  await expect(other.getByLabel("Your code")).not.toHaveText(code);

  // The old code finds nobody now.
  await toMembers(page);
  await page.getByRole("button", { name: "Invite someone" }).click();
  const sheet = page.getByRole("dialog", { name: "Invite someone" });
  await sheet.getByLabel("Their code").fill(code);
  await sheet.getByRole("button", { name: "Find" }).click();
  await expect(sheet.getByText(/No one has that code/)).toBeVisible();

  expect(otherProblems).toEqual([]);
});
