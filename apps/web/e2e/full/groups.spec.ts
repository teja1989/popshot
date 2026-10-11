import { expect, test, type Page } from "@playwright/test";

import { newUser, signIn, type TestUser } from "./auth";
import { watchProblems } from "./problems";

async function startGroup(page: Page, name: string): Promise<string> {
  await page.getByRole("button", { name: "Start a group" }).first().click();
  const dialog = page.getByRole("dialog", { name: "Start a group" });
  await dialog.getByLabel("Group name").fill(name);
  await dialog.getByRole("button", { name: "Create group" }).click();
  await expect(page).toHaveURL(/\/groups\/[0-9a-f-]{36}$/);
  return page.url();
}

test("start a group from the empty state and land on its page", async ({ page }) => {
  const casey: TestUser = newUser("Casey");
  await signIn(page, casey);
  const problems = await watchProblems(page);
  await page.goto("/");

  await expect(page.getByText("No groups yet.")).toBeVisible();
  await page.getByRole("button", { name: "Start a group" }).click();

  // A Radix dialog, under the production CSP: no violations (its scroll lock adds a
  // <style> that needs the page's nonce).
  const dialog = page.getByRole("dialog", { name: "Start a group" });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByLabel("Group name")).toBeFocused();

  await dialog.getByLabel("Group name").fill("  Tuesday Dinkers ");
  await dialog.getByText("Singles", { exact: true }).click();
  await dialog.getByText("15", { exact: true }).click();
  await dialog.getByRole("switch", { name: "Win by 2" }).uncheck();
  await dialog.getByRole("button", { name: "Create group" }).click();

  await expect(page).toHaveURL(/\/groups\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Tuesday Dinkers");
  await expect(page.getByText("Singles · games to 15", { exact: true })).toBeVisible();
  const members = page.getByRole("list").filter({ hasText: casey.name });
  await expect(members.getByRole("listitem")).toHaveCount(1);
  await expect(members).toContainText(`${casey.name} (you)`);
  await expect(members).toContainText("Lead");

  await page.getByRole("link", { name: "Your groups" }).click();
  const card = page.getByRole("link", { name: /Tuesday Dinkers/ });
  await expect(card).toContainText("Lead · 1 member");
  expect(problems).toEqual([]);
});

test("the dialog checks the name and closes cleanly", async ({ page }) => {
  await signIn(page, newUser("Alex"));
  const problems = await watchProblems(page);
  await page.goto("/");

  const trigger = page.getByRole("button", { name: "Start a group" });
  await trigger.click();
  const dialog = page.getByRole("dialog", { name: "Start a group" });
  await dialog.getByRole("button", { name: "Create group" }).click();
  await expect(dialog.getByRole("alert")).toHaveText("Give your group a name.");
  await expect(dialog.getByLabel("Group name")).toBeFocused();
  // The field stops at 60 characters, the API's limit.
  await dialog.getByLabel("Group name").fill("x".repeat(70));
  await expect(dialog.getByLabel("Group name")).toHaveValue("x".repeat(60));

  await page.keyboard.press("Escape");
  await expect(dialog).toBeHidden();
  await expect(trigger).toBeFocused();
  // Nothing was created.
  await expect(page.getByText("No groups yet.")).toBeVisible();
  expect(problems).toEqual([]);
});

test("someone outside a group can't open it", async ({ page, browser }) => {
  await signIn(page, newUser("Riley"));
  await page.goto("/");
  const url = await startGroup(page, "Riley's Crew");

  const other = await browser.newPage();
  await signIn(other, newUser("Sam"));
  await other.goto(url);
  await expect(other.getByRole("heading", { name: "We couldn't find that group." })).toBeVisible();
  await expect(other.getByText("Riley's Crew")).toHaveCount(0);
  // And it isn't in Sam's list.
  await other.goto("/");
  await expect(other.getByText("No groups yet.")).toBeVisible();
  await other.close();
});

test("a malformed group address is a 404 page", async ({ page }) => {
  await signIn(page, newUser("Jordan"));
  const response = await page.goto("/groups/not-a-real-id");
  expect(response?.status()).toBe(404);
  await expect(page.getByRole("heading", { name: "That page is out of bounds." })).toBeVisible();
});
