import { expect, test, type Page } from "@playwright/test";

import { newUser, signIn } from "./auth";
import { toMembers } from "./members";
import { watchProblems } from "./problems";

async function startGroup(page: Page, name: string): Promise<string> {
  await page.goto("/");
  await page.getByRole("button", { name: "Start a group" }).first().click();
  await page.getByLabel("Group name").fill(name);
  await page.getByRole("button", { name: "Create group" }).click();
  await expect(page).toHaveURL(/\/groups\/[0-9a-f-]{36}$/);
  return page.url();
}

async function invite(lead: Page, other: Page): Promise<void> {
  await toMembers(lead);
  await lead.getByRole("button", { name: "Make an invite link" }).click();
  await lead.getByRole("dialog", { name: "Make an invite link" }).getByText("Up to 5", { exact: true }).click();
  await lead.getByRole("dialog", { name: "Make an invite link" }).getByRole("button", { name: "Make link" }).click();
  const made = lead.getByRole("dialog", { name: "Your invite link" });
  const link = await made.getByLabel("Link").inputValue();
  await made.getByRole("button", { name: "Close" }).click();
  await other.goto(link);
  await other.getByRole("button", { name: "Ask to join" }).click();
  await expect(other.getByRole("heading", { name: "Waiting for approval" })).toBeVisible();
  await lead.reload();
}

test("plan a night, answer from Home, the waitlist moves up, then cancel", async ({ page, browser }) => {
  test.setTimeout(120_000);
  const casey = newUser("Casey");
  const riley = newUser("Riley");
  const alex = newUser("Alex");
  await signIn(page, casey);
  const problems = await watchProblems(page);
  const groupUrl = await startGroup(page, "Night Owls");

  const rileyPage = await browser.newPage();
  await signIn(rileyPage, riley);
  const alexPage = await browser.newPage();
  await signIn(alexPage, alex);
  for (const [other, person] of [
    [rileyPage, riley],
    [alexPage, alex],
  ] as const) {
    await invite(page, other);
    await page.getByRole("button", { name: `Let ${person.name} in` }).click();
    await expect(page.getByRole("region", { name: /Members/ })).toContainText(person.name);
  }

  // Casey plans a night with 2 spots, and is going.
  await page.goto(groupUrl);
  const nights = page.getByRole("region", { name: "Meetups" });
  await expect(nights).toContainText("Nothing planned yet");
  await nights.getByRole("button", { name: "Plan one" }).click();
  const sheet = page.getByRole("dialog", { name: "Plan a meetup" });
  await sheet.getByLabel("Where").fill("Riverside courts");
  await sheet.getByLabel("Spots").fill("2");
  await sheet.getByLabel("Note (optional)").fill("Bring balls");
  await sheet.getByRole("button", { name: "Plan it" }).click();
  await expect(sheet).toBeHidden();
  const card = nights.getByRole("article", { name: "Meetup at Riverside courts" });
  await expect(card).toContainText("Tomorrow · 6:00 PM");
  await expect(card).toContainText("1 going · 1 spot left");
  await expect(card).toContainText("You're in");

  // Riley answers from Home in one tap and takes the last spot.
  await rileyPage.goto("/");
  const next = rileyPage.getByRole("region", { name: "Next meetup" });
  await expect(next).toContainText("Night Owls");
  await next.getByText("I'm in", { exact: true }).click();
  await expect(next).toContainText("You're in");
  await expect(next).toContainText("Full");

  // Alex is waitlisted, then moves up when Riley drops out.
  await alexPage.goto(groupUrl);
  const alexCard = alexPage.getByRole("article", { name: "Meetup at Riverside courts" });
  await alexCard.getByText("I'm in", { exact: true }).click();
  await expect(alexCard).toContainText("You're 1st on the waitlist");
  await next.getByText("Can't go", { exact: true }).click();
  await expect(next).toContainText("You can't make it");
  await alexPage.reload();
  await expect(alexCard).toContainText("You're in");

  // The night's page lists everyone; Casey changes it, then cancels.
  await card.getByRole("link").click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Tomorrow · 6:00 PM");
  await expect(page.getByRole("region", { name: /Going · 2 of 2/ })).toContainText(alex.name);
  await expect(page.getByRole("region", { name: /Can't make it · 1/ })).toContainText(riley.name);
  await expect(page.getByText("Bring balls")).toBeVisible();
  await page.getByRole("button", { name: "Change details" }).click();
  const edit = page.getByRole("dialog", { name: "Change this meetup" });
  await edit.getByLabel("Where").fill("Hilltop courts");
  await edit.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Hilltop courts", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Cancel night" }).click();
  await page.getByRole("dialog", { name: "Cancel this meetup?" }).getByRole("button", { name: "Cancel night" }).click();
  await expect(page.getByText("Cancelled", { exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Your answer" })).toHaveCount(0);

  // Gone from Riley's Home.
  await rileyPage.reload();
  await expect(rileyPage.getByRole("region", { name: "Next meetup" })).toHaveCount(0);
  expect(problems).toEqual([]);
});
