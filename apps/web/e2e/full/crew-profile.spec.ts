import { expect, test } from "@playwright/test";

import { newUser, signIn } from "./auth";
import { watchProblems } from "./problems";

test("a lead fills in the crew profile; invited people see it without the courts", async ({ page, browser }) => {
  await signIn(page, newUser("Casey"));
  const problems = await watchProblems(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Start a group" }).first().click();
  await page.getByLabel("Group name").fill("Dawn Dinkers");
  await page.getByRole("button", { name: "Create group" }).click();
  await expect(page).toHaveURL(/\/groups\/[0-9a-f-]{36}$/);
  const groupUrl = page.url();

  await page.goto(`${groupUrl}/settings`);
  const profile = page.getByRole("region", { name: "Crew profile" });
  // Links are refused.
  await profile.getByLabel("About").fill("See www.dawndinkers.org");
  await profile.getByRole("button", { name: "Save profile" }).click();
  await expect(profile.getByRole("status")).toHaveText("Leave out links and web or email addresses.");
  await profile.getByLabel("About").fill("Friendly games, all levels.");
  await profile.getByText("Tue", { exact: true }).click();
  await profile.getByText("Sat", { exact: true }).click();
  await profile.getByText("Morning", { exact: true }).click();
  await profile.getByLabel("Home court 1").fill("Riverside Park courts");
  await profile.getByRole("button", { name: "Save profile" }).click();
  await expect(profile.getByRole("status")).toHaveText("Saved.");

  // Members see it all on the group page.
  await page.goto(groupUrl);
  await expect(page.getByText("Friendly games, all levels.")).toBeVisible();
  await expect(page.getByText("Usually Tue and Sat · mornings")).toBeVisible();
  await expect(page.getByText("Plays at Riverside Park courts")).toBeVisible();

  // Someone with an invite link sees about and times, not the courts.
  await page.goto(`${groupUrl}/members`);
  await page.getByRole("button", { name: "Make an invite link" }).click();
  await page.getByRole("dialog", { name: "Make an invite link" }).getByRole("button", { name: "Make link" }).click();
  const link = await page.getByRole("dialog", { name: "Your invite link" }).getByLabel("Link").inputValue();
  const other = await browser.newPage();
  await signIn(other, newUser("Riley"));
  await other.goto(link);
  await expect(other.getByRole("heading", { name: "Dawn Dinkers" })).toBeVisible();
  await expect(other.getByText("Friendly games, all levels.")).toBeVisible();
  await expect(other.getByText("Usually Tue and Sat · mornings")).toBeVisible();
  await expect(other.getByText(/Riverside/)).toHaveCount(0);

  expect(problems).toEqual([]);
});
