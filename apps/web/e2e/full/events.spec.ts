import { expect, test, type Page } from "@playwright/test";

import { apiAs } from "./api";
import { newUser, signIn, type TestUser } from "./auth";
import { watchProblems } from "./problems";

// dev/run.sh makes this address the admin.
const ADMIN: TestUser = { name: "Admin Test", email: "admin@popshot.test" };
const GUESTS = ["Ana", "Bo", "Cy", "Di", "Ed", "Flo", "Gus", "Hal"];

/** A crew led by `lead`, with guests, switched on for `features`. Returns its id. */
async function crewWithEvents(page: Page, lead: TestUser, guests: string[], features: string[]): Promise<string> {
  await signIn(page, lead);
  await page.goto("/");
  const crew = (await apiAs(page, "POST", "/v1/groups", { name: `Events ${String(Date.now())}` })) as { id: string };
  for (const name of guests) {
    await apiAs(page, "POST", `/v1/groups/${crew.id}/players`, { display_name: name });
  }
  await signIn(page, ADMIN);
  await page.goto("/");
  for (const key of features) {
    await apiAs(page, "POST", `/v1/admin/features/crews/${crew.id}`, {
      key,
      reason: "Browser test: events beta for this crew.",
    });
  }
  await signIn(page, lead);
  return crew.id;
}

async function scoreCourt(page: Page, court: number, a: string, b: string) {
  const card = page.getByRole("article", { name: `Court ${String(court)}` });
  const boxes = card.getByRole("textbox");
  await boxes.nth(0).fill(a);
  await boxes.nth(1).fill(b);
  await card.getByRole("button", { name: "Save score" }).click();
  await expect(card.getByRole("button", { name: "Save score" })).toHaveCount(0);
}

test("a lead runs a Dink Shuffle from Play: rounds, scores, finish", async ({ page }) => {
  test.setTimeout(120_000);
  const lead = newUser("Nia");
  await crewWithEvents(page, lead, GUESTS, ["events.shuffle"]);
  const problems = await watchProblems(page);

  await page.goto("/play");
  const events = page.getByRole("region", { name: "Events" });
  await events.getByRole("link", { name: "Start one" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Start an event");
  // Only Dink Shuffle is on, so it's already picked.
  await expect(page.getByRole("radio", { name: /Dink Shuffle/ })).toBeChecked();
  for (const name of [lead.name, ...GUESTS]) {
    await page.getByRole("checkbox", { name }).check();
  }
  await expect(page.getByText("8 play each round on 2 courts, 1 sits out.").first()).toBeVisible();
  await page.getByLabel("Name").fill("Saturday Shuffle");
  await page.getByRole("button", { name: "Start round 1" }).click();

  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Saturday Shuffle");
  await expect(page.getByRole("region", { name: "Round 1" })).toBeVisible();
  await expect(page.getByText(/^Sitting out: /)).toBeVisible();
  await expect(page.getByRole("button", { name: "Start round 2" })).toBeDisabled();

  // A bad score is explained before saving.
  const court1 = page.getByRole("article", { name: "Court 1" });
  await court1.getByRole("textbox").nth(0).fill("11");
  await court1.getByRole("textbox").nth(1).fill("10");
  await expect(court1.getByText("Past game point, the winner finishes exactly two points ahead.")).toBeVisible();

  await scoreCourt(page, 1, "11", "7");
  await scoreCourt(page, 2, "9", "11");
  await page.getByRole("button", { name: "Start round 2" }).click();
  await expect(page.getByRole("region", { name: "Round 2" })).toBeVisible();
  // Round 1 is folded away with its scores.
  await page.getByText("Round 1", { exact: true }).click();
  await expect(page.getByText("11–7")).toBeVisible();

  await page.getByRole("button", { name: "Finish event" }).click();
  await page.getByRole("button", { name: "Yes, finish" }).click();
  await expect(page.getByText("That's a wrap. Every game is on the crew's record.")).toBeVisible();
  await expect(page.getByRole("link", { name: "See the recap on Crew →" })).toHaveAttribute("href", "/crew");

  // Back on Play: the event is listed as finished, and its games are ordinary games.
  await page.goto("/play");
  await expect(events.getByRole("link", { name: /Saturday Shuffle/ })).toContainText("Finished");
  expect(problems).toEqual([]);
});

test("Ride the River moves the winners up, and Competitive shows standings", async ({ page }) => {
  test.setTimeout(120_000);
  const lead = newUser("Oz");
  const guests = GUESTS.slice(0, 7);
  const crewId = await crewWithEvents(page, lead, guests, ["events.shuffle", "events.river"]);
  const problems = await watchProblems(page);

  await page.goto(`/groups/${crewId}/events/new`);
  // The options are hidden radios inside their labels: tap the label, as a person would.
  await page.getByText("Ride the River", { exact: true }).click();
  for (const name of [lead.name, ...guests]) {
    await page.getByRole("checkbox", { name }).check();
  }
  await page.getByText("By crew points", { exact: true }).click();
  await page.getByText("Competitive", { exact: true }).click();
  await page.getByRole("button", { name: "Start round 1" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Ride the River");

  const top = page.getByRole("article", { name: "Court 1" });
  const topWinners = (await top.locator("p span").nth(0).textContent()) ?? "";
  await scoreCourt(page, 1, "11", "4");
  await scoreCourt(page, 2, "11", "6");
  // Competitive: a table, inside this event only.
  await expect(page.getByRole("region", { name: "Standings, this event only" })).toBeVisible();
  await page.getByRole("button", { name: "Start round 2" }).click();
  await expect(page.getByRole("region", { name: "Round 2" })).toBeVisible();
  // The top court's winners stay on top, now with new partners.
  const newTop = page.getByRole("region", { name: "Round 2" }).getByRole("article", { name: "Court 1" });
  for (const name of topWinners.split(" & ")) {
    await expect(newTop).toContainText(name);
  }
  expect(problems).toEqual([]);
});

test("without the switch there's no Events section and no way to start one", async ({ page }) => {
  await signIn(page, newUser("Pia"));
  await page.goto("/");
  const crew = (await apiAs(page, "POST", "/v1/groups", { name: `No events ${String(Date.now())}` })) as {
    id: string;
  };
  await page.goto("/play");
  await expect(page.getByRole("heading", { name: "Meetups" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Events" })).toHaveCount(0);
  await page.goto(`/groups/${crew.id}/events/new`);
  await expect(page.getByText(/Events aren't switched on for/)).toBeVisible();
});
