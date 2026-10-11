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

async function makeLink(page: Page): Promise<string> {
  await page.getByRole("button", { name: "Make an invite link" }).click();
  const dialog = page.getByRole("dialog", { name: "Make an invite link" });
  await dialog.getByText("Up to 5", { exact: true }).click();
  await dialog.getByRole("button", { name: "Make link" }).click();
  const made = page.getByRole("dialog", { name: "Your invite link" });
  const link = await made.getByLabel("Link").inputValue();
  await made.getByRole("button", { name: "Close" }).click();
  return link;
}

test("settings, handing over, leaving, restoring, deleting and restoring a group", async ({ page, browser }) => {
  test.setTimeout(120_000);
  const casey = newUser("Casey");
  const riley = newUser("Riley");
  await signIn(page, casey);
  const problems = await watchProblems(page);
  const groupUrl = await startGroup(page, "Thursday Smashers");

  // Rename and change the usual rules.
  await page.getByRole("button", { name: "Group settings" }).click();
  const settings = page.getByRole("dialog", { name: "Group settings" });
  await settings.getByLabel("Group name").fill("Night Owls");
  await settings.getByText("Singles", { exact: true }).click();
  await settings.getByText("15", { exact: true }).click();
  await settings.getByRole("button", { name: "Save" }).click();
  await expect(settings).toBeHidden();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Night Owls");
  await expect(page.getByText("Singles · games to 15, win by 2")).toBeVisible();

  // Riley joins.
  const link = await makeLink(page);
  const other = await browser.newPage();
  await signIn(other, riley);
  await other.goto(link);
  await other.getByRole("button", { name: "Ask to join" }).click();
  await page.reload();
  await page.getByRole("button", { name: `Let ${riley.name} in` }).click();
  const members = page.getByRole("region", { name: /Members/ });
  await expect(members).toContainText(riley.name);

  // The lead can't just leave; they hand over first.
  await expect(page.getByText("To leave, make someone else the lead first")).toBeVisible();
  await expect(page.getByRole("button", { name: "Leave group" })).toHaveCount(0);
  await page.getByRole("button", { name: `Manage ${riley.name}` }).click();
  const manage = page.getByRole("dialog", { name: riley.name });
  await manage.getByRole("button", { name: /^Make lead/ }).click();
  await manage.getByRole("button", { name: "Make lead", exact: true }).click();
  await expect(manage).toBeHidden();
  await expect(members.getByRole("listitem").filter({ hasText: riley.name })).toContainText("Lead");
  await expect(members.getByRole("listitem").filter({ hasText: casey.name })).toContainText("Co-lead");

  // Casey leaves; Riley (now lead) sees Casey gone and not offered for restoring.
  await page.getByRole("button", { name: "Leave group" }).click();
  await page.getByRole("dialog", { name: "Leave Night Owls?" }).getByRole("button", { name: "Leave", exact: true }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByText("Night Owls")).toHaveCount(0);
  await other.goto(groupUrl);
  await expect(other.getByRole("region", { name: /Members · 1/ })).toBeVisible();
  await expect(other.getByRole("region", { name: /Removed or declined/ })).toHaveCount(0);

  // Casey asks to come back with a fresh link; Riley lets them in, then removes and restores.
  const back = await makeLink(other);
  await page.goto(back);
  await page.getByRole("button", { name: "Ask to join" }).click();
  await expect(page.getByRole("heading", { name: "Waiting for approval" })).toBeVisible();
  await other.reload();
  await other.getByRole("button", { name: `Let ${casey.name} in` }).click();
  await other.getByRole("button", { name: `Manage ${casey.name}` }).click();
  const manageCasey = other.getByRole("dialog", { name: casey.name });
  await manageCasey.getByRole("button", { name: /Remove from group/ }).click();
  await manageCasey.getByRole("button", { name: "Remove", exact: true }).click();
  const former = other.getByRole("region", { name: /Removed or declined/ });
  await expect(former).toContainText(casey.name);
  await other.getByRole("button", { name: `Restore ${casey.name}` }).click();
  await expect(former).toHaveCount(0);
  await expect(other.getByRole("region", { name: /Members · 2/ })).toBeVisible();

  // Riley deletes the group (typing its name), then restores it from Home.
  await other.getByRole("button", { name: "Delete group" }).click();
  const confirm = other.getByRole("dialog", { name: "Delete Night Owls?" });
  const go = confirm.getByRole("button", { name: "Delete group" });
  await expect(go).toBeDisabled();
  await confirm.getByLabel("Type the group's name to confirm").fill("Night Owls");
  await go.click();
  await expect(other).toHaveURL(/\/$/);
  const deleted = other.getByRole("region", { name: "Recently deleted" });
  await expect(deleted).toContainText("Night Owls");
  await expect(deleted).toContainText("30 days left to restore");
  // Gone for Casey too.
  await page.goto(groupUrl);
  await expect(page.getByRole("heading", { name: "We couldn't find that group." })).toBeVisible();

  await other.getByRole("button", { name: "Restore Night Owls" }).click();
  await expect(other).toHaveURL(groupUrl);
  await expect(other.getByRole("heading", { level: 1 })).toHaveText("Night Owls");
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Night Owls");
  // Casey's 404 above was expected.
  expect(problems.filter((p) => !p.includes("404"))).toEqual([]);
});
