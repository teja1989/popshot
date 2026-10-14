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

// The check-in list and page. The scheduled job makes check-ins every two weeks, which a browser
// test can't wait for, so these two API answers are stood in for here; making and writing them
// is covered by the API's database tests (tests/db/test_journey_checkins_api.py).
const CHECKIN = {
  id: "0b6f2a4e-6a1c-4d55-9a57-3d1b2c4e5f60",
  period_start: "2026-09-30T10:00:00Z",
  period_end: "2026-10-14T10:00:00Z",
  ready: true,
  chapter: "Building rallies",
  headline: "6 games in two weeks of pickleball",
  opened: false,
  lines: ["You played 6 games on 3 days and won 4, 2 of them close.", "You teamed up most with Sam (3 games)."],
  try_next: "Count your dinks today. Ten in a row, cross-court.",
  picks: [
    {
      id: "5c1d1e0a-8f0e-4a63-9a2b-1c2d3e4f5a6b",
      kind: "video",
      url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      title: "Dinking basics",
      source: "A Coach",
      skills: ["dinking_patience"],
      minutes: 8,
    },
  ],
  // Gemini wrote it: the app never says so.
  written_by: "ai",
  new_chapter: true,
};

test("a check-in shows on the Journey tab and opens, with no word about who wrote it", async ({ page }) => {
  await crewWithJourney(page, newUser("Rae"));
  const problems = await watchProblems(page);
  await page.route("**/v1/me/journey/checkins", (route) =>
    route.fulfill({
      json: [
        {
          id: CHECKIN.id,
          period_start: CHECKIN.period_start,
          period_end: CHECKIN.period_end,
          ready: false,
          chapter: null,
          headline: null,
          opened: false,
        },
      ],
    }),
  );
  await page.route(`**/v1/me/journey/checkins/${CHECKIN.id}`, (route) => route.fulfill({ json: CHECKIN }));

  await page.goto("/you/journey");
  const list = page.getByRole("list", { name: "Your check-ins" });
  const item = list.getByRole("link");
  await expect(item).toContainText("Ready when you are");
  await expect(item).toContainText("New");
  await item.click();

  await expect(page).toHaveURL(new RegExp(`/you/journey/checkins/${CHECKIN.id}$`));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(CHECKIN.headline);
  await expect(page.locator("[data-new-chapter]")).toHaveText("New chapter: Building rallies");
  await expect(page.getByText("You teamed up most with Sam (3 games).")).toBeVisible();
  await expect(page.getByRole("region", { name: "Try next" })).toContainText("Count your dinks today.");
  const pick = page.getByRole("region", { name: "Picked for you" }).getByRole("link", { name: /Dinking basics/ });
  await expect(pick).toHaveAttribute("rel", "noopener noreferrer");
  await expect(pick).toHaveAttribute("target", "_blank");
  await expect(page.getByText(/\bAI\b|Gemini/)).toHaveCount(0);

  await page.getByRole("link", { name: "Your journey" }).click();
  await expect(page).toHaveURL(/\/you\/journey$/);
  expect(problems).toEqual([]);
});

test("a check-in that isn't yours, or isn't there, is a friendly not found", async ({ page }) => {
  await crewWithJourney(page, newUser("Sol"));
  await page.goto("/you/journey/checkins/0b6f2a4e-6a1c-4d55-9a57-3d1b2c4e5f61");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("We couldn't find that check-in.");
  await page.goto("/you/journey/checkins/not-a-check-in");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText("We couldn't find that check-in.")).toHaveCount(0);
});

async function turnOnPersonal(page: Page, lead: TestUser): Promise<void> {
  const crews = (await apiAs(page, "GET", "/v1/groups")) as { id: string }[];
  await signIn(page, ADMIN);
  await page.goto("/");
  for (const crew of crews) {
    await apiAs(page, "POST", `/v1/admin/features/crews/${crew.id}`, {
      key: "you.journey_ai",
      reason: "Browser test: personal check-ins for this crew.",
    });
  }
  await signIn(page, lead);
}

test("personal check-ins: asked once, 'Not now' sticks here, and the switch says yes or no", async ({ page }) => {
  const lead = newUser("Tam");
  await crewWithJourney(page, lead);
  await page.goto("/");
  await turnOnPersonal(page, lead);
  const problems = await watchProblems(page);

  await page.goto("/you/journey");
  const card = page.getByRole("region", { name: "Make your check-ins more personal?" });
  await expect(card).toContainText("Uses Google Gemini");
  await expect(page.getByText(/\bAI\b/)).toHaveCount(0);
  const toggle = page.getByRole("region", { name: "Personal check-ins" }).getByRole("switch");
  await expect(toggle).not.toBeChecked();

  // Not now: gone, and still gone after a reload on this device.
  await card.getByRole("button", { name: "Not now" }).click();
  await expect(card).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole("heading", { level: 1, name: "Your journey" })).toBeVisible();
  await expect(toggle).toBeVisible();
  await expect(card).toHaveCount(0);

  // The switch saves yes, on the server.
  await toggle.click();
  await expect(toggle).toBeChecked();
  expect(
    ((await apiAs(page, "GET", "/v1/me/journey")) as { settings: { ai_consent: boolean } }).settings.ai_consent,
  ).toBe(true);
  await page.reload();
  await expect(toggle).toBeChecked();
  await toggle.click();
  await expect(toggle).not.toBeChecked();
  expect(
    ((await apiAs(page, "GET", "/v1/me/journey")) as { settings: { ai_consent: boolean } }).settings.ai_consent,
  ).toBe(false);
  expect(problems).toEqual([]);
});

test("personal check-ins: 'Yes' from the card is saved, and the card goes", async ({ page }) => {
  const lead = newUser("Uma");
  await crewWithJourney(page, lead);
  await page.goto("/");
  await turnOnPersonal(page, lead);
  await page.goto("/you/journey");
  const card = page.getByRole("region", { name: "Make your check-ins more personal?" });
  await card.getByRole("button", { name: "Yes, personalise" }).click();
  await expect(card).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Personal check-ins" }).getByRole("switch")).toBeChecked();
});

test("with personal check-ins switched off, there's no question and no switch", async ({ page }) => {
  await crewWithJourney(page, newUser("Val"));
  await page.goto("/you/journey");
  await expect(page.getByRole("heading", { level: 1, name: "Your journey" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Your story" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Make your check-ins more personal?" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "Personal check-ins" })).toHaveCount(0);
});
