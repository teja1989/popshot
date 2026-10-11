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

async function makeLink(page: Page, uses: "1 person" | "Up to 5" | "Up to 10"): Promise<string> {
  await page.getByRole("button", { name: "Make an invite link" }).click();
  const dialog = page.getByRole("dialog", { name: "Make an invite link" });
  await dialog.getByText(uses, { exact: true }).click();
  await dialog.getByRole("button", { name: "Make link" }).click();
  const made = page.getByRole("dialog", { name: "Your invite link" });
  const link = await made.getByLabel("Link").inputValue();
  expect(link).toMatch(/\/join#[A-Za-z0-9_-]{43}$/);
  await made.getByRole("button", { name: "Close" }).click();
  await expect(made).toBeHidden();
  return link;
}

test("invite someone, let them in, promote them, then remove them", async ({ page, browser }) => {
  const casey = newUser("Casey");
  const riley = newUser("Riley");
  await signIn(page, casey);
  const problems = await watchProblems(page);
  const groupUrl = await startGroup(page, "Thursday Smashers");

  const link = await makeLink(page, "Up to 5");
  const open = page.getByRole("list", { name: "Open invite links" });
  await expect(open.getByRole("listitem")).toHaveCount(1);
  await expect(open).toContainText("For up to 5 people");
  await expect(open).toContainText("0 joined");
  await expect(open).toContainText("Expires in 7 days");

  // Signed out, the link explains itself and offers sign-in. Nothing about the group yet.
  const guest = await browser.newPage();
  await guest.goto(link);
  await expect(guest.getByText("You've been invited")).toBeVisible();
  await expect(guest.getByRole("button", { name: "Continue with Google" }).first()).toBeVisible();
  await expect(guest.getByText("Thursday Smashers")).toHaveCount(0);

  await signIn(guest, riley);
  const guestProblems = await watchProblems(guest);
  await guest.goto(link);
  await expect(guest.getByText(`${casey.name} invited you`)).toBeVisible();
  await expect(guest.getByRole("heading", { name: "Thursday Smashers" })).toBeVisible();
  // The token is taken out of the address bar once read.
  await expect.poll(() => guest.url()).not.toContain("#");
  await guest.getByRole("button", { name: "Ask to join" }).click();
  await expect(guest).toHaveURL(groupUrl);
  await expect(guest.getByRole("heading", { name: "Waiting for approval" })).toBeVisible();

  // The lead sees the request and lets Riley in.
  await page.reload();
  const asking = page.getByRole("region", { name: /Asking to join/ });
  await expect(asking).toContainText(riley.name);
  await page.getByRole("button", { name: `Let ${riley.name} in` }).click();
  await expect(asking).toBeHidden();
  const members = page.getByRole("region", { name: /Members/ });
  await expect(members).toContainText(riley.name);
  await expect(open).toContainText("1 joined");

  // Riley is in, as a plain member who can't invite.
  await guest.reload();
  await expect(guest.getByRole("region", { name: /Members · 2/ })).toBeVisible();
  await expect(guest.getByText("Ask the lead or a co-lead for an invite link.")).toBeVisible();
  await expect(guest.getByRole("button", { name: "Make an invite link" })).toHaveCount(0);

  // Promote to co-lead.
  await page.getByRole("button", { name: `Manage ${riley.name}` }).click();
  await page.getByRole("dialog", { name: riley.name }).getByRole("button", { name: /Make co-lead/ }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(members.getByRole("listitem").filter({ hasText: riley.name })).toContainText("Co-lead");
  await guest.reload();
  await expect(guest.getByRole("button", { name: "Make an invite link" })).toBeVisible();

  // Remove, with a confirmation step.
  await page.getByRole("button", { name: `Manage ${riley.name}` }).click();
  const manage = page.getByRole("dialog", { name: riley.name });
  await manage.getByRole("button", { name: /Remove from group/ }).click();
  await manage.getByRole("button", { name: "Remove", exact: true }).click();
  await expect(manage).toBeHidden();
  await expect(members).not.toContainText(riley.name);
  expect(problems).toEqual([]);
  // From here Riley's requests are expected 404s.
  expect(guestProblems).toEqual([]);
  await guest.reload();
  await expect(guest.getByRole("heading", { name: "We couldn't find that group." })).toBeVisible();
  await guest.close();
});

test("declining, and links that stop working", async ({ page, browser }) => {
  const casey = newUser("Casey");
  await signIn(page, casey);
  await startGroup(page, "Weekend Smash");
  const single = await makeLink(page, "1 person");

  const alex = await browser.newPage();
  await signIn(alex, newUser("Alex"));
  await alex.goto(single);
  await alex.getByRole("button", { name: "Ask to join" }).click();
  await expect(alex.getByRole("heading", { name: "Waiting for approval" })).toBeVisible();
  // Opening the used single-use link again shows the request, not an error.
  await alex.goto(single);
  await expect(alex.getByText("You've asked to join.")).toBeVisible();

  // Someone else can't use it: it's used up.
  const sam = await browser.newPage();
  await signIn(sam, newUser("Sam"));
  await sam.goto(single);
  await expect(sam.getByRole("heading", { name: "This invite link isn't valid any more." })).toBeVisible();

  // The lead declines Alex, who then can't get back in with a fresh link.
  await page.reload();
  await page.getByRole("button", { name: /^Decline / }).click();
  await expect(page.getByRole("region", { name: /Asking to join/ })).toBeHidden();
  const fresh = await makeLink(page, "1 person");
  await alex.goto(fresh);
  await expect(alex.getByText("You can't join this group with this link.")).toBeVisible();
  await expect(alex.getByRole("button", { name: "Ask to join" })).toHaveCount(0);

  // A cancelled link stops working.
  await page.getByRole("button", { name: "Cancel link" }).click();
  await expect(page.getByRole("list", { name: "Open invite links" })).toBeHidden();
  await sam.goto(fresh);
  await expect(sam.getByRole("heading", { name: "This invite link isn't valid any more." })).toBeVisible();

  // A link with no token.
  await sam.goto("/join");
  await expect(sam.getByRole("heading", { name: "Open your invite link again." })).toBeVisible();
  await alex.close();
  await sam.close();
});
