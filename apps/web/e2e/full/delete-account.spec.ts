import { expect, test } from "@playwright/test";

import { newUser, signIn } from "./auth";
import { watchProblems } from "./problems";

test("download your data, ask to delete your account, then keep it", async ({ page }) => {
  await signIn(page, newUser("Dana"));
  const problems = await watchProblems(page);
  await page.goto("/you/settings");
  const data = page.getByRole("region", { name: "Your data" });

  const download = page.waitForEvent("download");
  await data.getByRole("button", { name: "Download my data" }).click();
  expect((await download).suggestedFilename()).toMatch(/^popshot-data-\d{4}-\d{2}-\d{2}\.json$/);

  await data.getByRole("button", { name: "Delete my account" }).click();
  const sheet = page.getByRole("dialog", { name: "Delete your account?" });
  const go = sheet.getByRole("button", { name: "Delete my account in 7 days" });
  await expect(go).toBeDisabled();
  await sheet.getByLabel("I understand").check();
  await go.click();
  await expect(sheet).toBeHidden();
  await expect(data).toContainText("Your account will be deleted on");

  // Home says so too, with the way back.
  await page.goto("/");
  await expect(page.getByText("Your account will be deleted on")).toBeVisible();
  await page.getByRole("link", { name: "Keep my account" }).click();
  await page.getByRole("region", { name: "Your data" }).getByRole("button", { name: "Keep my account" }).click();
  await expect(page.getByText("Your account stays.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Delete my account" })).toBeVisible();
  expect(problems).toEqual([]);
});

test("a lead with crewmates is asked to hand over first", async ({ page, browser }) => {
  await signIn(page, newUser("Lee"));
  await page.goto("/");
  await page.getByRole("button", { name: "Start a group" }).first().click();
  await page.getByLabel("Group name").fill("Night Owls");
  await page.getByRole("button", { name: "Create group" }).click();
  await expect(page).toHaveURL(/\/groups\/[0-9a-f-]{36}$/);
  await page.goto(`${page.url()}/members`);
  await page.getByRole("button", { name: "Make an invite link" }).click();
  await page.getByRole("dialog", { name: "Make an invite link" }).getByRole("button", { name: "Make link" }).click();
  const link = await page.getByRole("dialog", { name: "Your invite link" }).getByLabel("Link").inputValue();
  const other = await browser.newPage();
  const sam = newUser("Sam");
  await signIn(other, sam);
  await other.goto(link);
  await other.getByRole("button", { name: "Ask to join" }).click();
  await page.reload();
  await page.getByRole("button", { name: `Let ${sam.name} in` }).click();

  await page.goto("/you/settings");
  await page.getByRole("button", { name: "Delete my account" }).click();
  const sheet = page.getByRole("dialog", { name: "Delete your account?" });
  await sheet.getByLabel("I understand").check();
  await sheet.getByRole("button", { name: "Delete my account in 7 days" }).click();
  await expect(sheet.getByRole("alert")).toContainText("First make someone else the lead of Night Owls");
});
