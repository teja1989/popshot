import { expect, test, type Page } from "@playwright/test";

import { apiAs } from "./api";
import { newUser, signIn, type TestUser } from "./auth";
import { watchProblems } from "./problems";

// Your journey (the Journey tab of You): behind the per-person 'you.journey' switch, which the
// admin turns on here for one crew, so its members get it.

// dev/run.sh makes this address the admin.
const ADMIN: TestUser = { name: "Admin Test", email: "admin@popshot.test" };

async function crewWithJourney(page: Page, lead: TestUser): Promise<void> {
  await signIn(page, lead);
  await page.goto("/");
  const crew = (await apiAs(page, "POST", "/v1/groups", { name: `Journey ${String(Date.now())}` })) as { id: string };
  await signIn(page, ADMIN);
  await page.goto("/");
  await apiAs(page, "POST", `/v1/admin/features/crews/${crew.id}`, {
    key: "you.journey",
    reason: "Browser test: journey beta for this crew.",
  });
  await signIn(page, lead);
}

test("with the journey off, there are no tabs and no story card", async ({ page }) => {
  await signIn(page, newUser("Ola"));
  await page.goto("/you");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "You" })).toHaveCount(0);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Your groups" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "What's your pickleball story?" })).toHaveCount(0);
  await page.goto("/you/journey");
  await expect(page.getByText("isn't switched on for you yet")).toBeVisible();
});

test("tell your story from Home, then grow it on the Journey tab", async ({ page }) => {
  const lead = newUser("Pia");
  await crewWithJourney(page, lead);
  const problems = await watchProblems(page);

  // Home asks once.
  await page.goto("/");
  const prompt = page.getByRole("region", { name: "What's your pickleball story?" });
  await expect(prompt).toBeVisible();
  await prompt.getByRole("button", { name: "Tell your story" }).click();
  const sheet = page.getByRole("dialog", { name: "Your story" });
  await sheet.getByRole("button", { name: "Save your story" }).click();
  await expect(sheet.getByRole("alert")).toHaveText("Write a few words in any of the boxes first.");
  await sheet.getByRole("textbox", { name: "How did you get into pickleball?" }).fill("A friend dragged me along.");
  await sheet.getByRole("textbox", { name: "What would you like to get better at?" }).fill("Dinks into the net.");
  await sheet
    .getByRole("group", { name: "Skills to work on" })
    .getByRole("button", { name: "Backhand consistency" })
    .click();
  await sheet.getByRole("button", { name: "Save your story" }).click();
  await expect(sheet).toHaveCount(0);
  await expect(prompt).toHaveCount(0);

  // The You tabs.
  await page.goto("/you");
  const tabs = page.getByRole("navigation", { name: "You" });
  await expect(tabs.getByRole("link", { name: "Me" })).toHaveAttribute("aria-current", "page");
  await tabs.getByRole("link", { name: "Journey" }).click();
  await expect(page).toHaveURL(/\/you\/journey$/);
  await expect(page.getByRole("heading", { level: 1, name: "Your journey" })).toBeVisible();
  await expect(tabs.getByRole("link", { name: "Journey" })).toHaveAttribute("aria-current", "page");

  // Today's tip is about the skill you're working on.
  const today = page.getByRole("region", { name: "Today's one thing" });
  await expect(today.getByText("Backhand consistency")).toBeVisible();

  // The story, and one day of learning so far.
  const story = page.getByRole("region", { name: "Your story" });
  await expect(story.getByText("A friend dragged me along.")).toBeVisible();
  await expect(story.getByText("Working on: Backhand consistency")).toBeVisible();
  await expect(page.locator("[data-learning-days]")).toHaveText("1 learning day");

  // A learning note.
  const notes = page.getByRole("region", { name: "What did you learn today?" });
  await notes.getByRole("textbox").fill("Soft hands on the reset.");
  await notes.getByRole("button", { name: "Backhand consistency" }).click();
  await notes.getByRole("button", { name: "Save note" }).click();
  const list = notes.getByRole("list", { name: "Your learning notes" });
  await expect(list.getByText("Soft hands on the reset.")).toBeVisible();
  await expect(notes.getByRole("textbox")).toHaveValue("");

  // Update the story: the earlier version is kept.
  await story.getByRole("button", { name: "Update your story" }).click();
  await page.getByRole("textbox", { name: "A goal for the next month" }).fill("Ten dinks in a row.");
  await page.getByRole("button", { name: "Save your story" }).click();
  await expect(story.getByText("Ten dinks in a row.")).toBeVisible();
  await story.getByText("1 earlier version").click();
  await expect(story.getByRole("listitem").filter({ hasText: "A friend dragged me along." })).toHaveCount(1);

  // Delete the note.
  await list.getByRole("button", { name: "Delete note: Soft hands on the reset." }).click();
  await expect(notes.getByRole("list", { name: "Your learning notes" })).toHaveCount(0);

  // Back goes to Me.
  await page.goBack();
  await expect(page).toHaveURL(/\/you$/);
  expect(problems).toEqual([]);
});

test("'Not now' on the story card sticks", async ({ page }) => {
  await crewWithJourney(page, newUser("Quin"));
  await page.goto("/");
  const prompt = page.getByRole("region", { name: "What's your pickleball story?" });
  await prompt.getByRole("button", { name: "Not now" }).click();
  await expect(prompt).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { name: "Your groups" })).toBeVisible();
  await expect(prompt).toHaveCount(0);
  // The story can still be written from the Journey tab.
  await page.goto("/you/journey");
  await expect(
    page.getByRole("region", { name: "Your story" }).getByRole("button", { name: "Tell your story" }),
  ).toBeVisible();
});
