import { expect, test, type Page } from "@playwright/test";

import { apiAs } from "./api";
import { newUser, signIn, type TestUser } from "./auth";
import { watchProblems } from "./problems";

// dev/run.sh makes this address the admin, and runs the API with made-up courts (FakePlaces).
const ADMIN: TestUser = { name: "Admin Test", email: "admin@popshot.test" };

/** Turn court search on or off for a crew as the admin, then sign `lead` back in. */
async function setSwitch(page: Page, crewId: string, lead: TestUser, on: boolean): Promise<void> {
  await signIn(page, ADMIN);
  await page.goto("/");
  await apiAs(page, "POST", `/v1/admin/features/crews/${crewId}${on ? "" : "/remove"}`, {
    key: "courts.places",
    reason: "Browser test: court search for this crew.",
  });
  await signIn(page, lead);
}

/** A crew led by `lead`, with court search on when `search` is true. Returns its id. */
async function crew(page: Page, lead: TestUser, search: boolean): Promise<string> {
  await signIn(page, lead);
  await page.goto("/");
  const made = (await apiAs(page, "POST", "/v1/groups", { name: `Courts ${String(Date.now())}` })) as { id: string };
  if (search) {
    await setSwitch(page, made.id, lead, true);
  }
  return made.id;
}

test("a lead saves courts, picks the default, and meetups start there", async ({ page }) => {
  test.setTimeout(90_000);
  const crewId = await crew(page, newUser("Rio"), true);
  const groupUrl = `/groups/${crewId}`;
  const problems = await watchProblems(page);

  await page.goto(`${groupUrl}/settings`);
  const courts = page.getByRole("region", { name: "Courts" });
  await expect(courts).toContainText("No courts saved yet.");

  // From Google: Google's name shows, the crew names it in its own words.
  await courts.getByRole("button", { name: "Find on the map" }).click();
  await courts.getByLabel("Search for your court").fill("park");
  const found = courts.getByRole("list", { name: "Courts found" });
  await expect(found.getByRole("button")).toHaveCount(2);
  await expect(courts.getByText("Results from Google Maps")).toBeVisible();
  await found.getByRole("button", { name: /Riverside Park Pickleball Courts/ }).click();
  const name = courts.getByLabel("What does your crew call it?");
  await expect(name).toBeFocused();
  await expect(name).toHaveValue("");
  await name.fill("Riverside courts");
  await courts.getByRole("button", { name: "Save court" }).click();
  await expect(courts.getByRole("status")).toHaveText("Saved.");

  // The first court is the default, with a Maps link.
  const saved = courts.getByRole("list", { name: "Saved courts" });
  const riverside = saved.getByRole("listitem").filter({ hasText: "Riverside courts" });
  await expect(riverside).toContainText("Default");
  const maps = riverside.getByRole("link", { name: /Open in Maps/ });
  await expect(maps).toHaveAttribute("target", "_blank");
  await expect(maps).toHaveAttribute("rel", "noopener noreferrer");
  await expect(maps).toHaveAttribute(
    "href",
    /^https:\/\/www\.google\.com\/maps\/search\/.*query_place_id=fake-riverside-park/,
  );

  // A typed court, made the default.
  await courts.getByRole("button", { name: "Type a name" }).click();
  await courts.getByLabel("Court name").fill("St James hall");
  await courts.getByRole("button", { name: "Save court" }).click();
  await expect(courts.getByRole("status")).toHaveText("Saved.");
  await courts.getByRole("button", { name: "Make St James hall the default" }).click();
  await expect(saved.getByRole("listitem").first()).toContainText("St James hall");
  await expect(saved.getByRole("listitem").first()).toContainText("Default");

  // Members see them on the crew page, default first.
  await page.goto(groupUrl);
  await expect(page.getByText("Plays at St James hall, Riverside courts")).toBeVisible();
  await expect(page.getByRole("link", { name: "Open Riverside courts in Maps" })).toHaveAttribute(
    "href",
    /query_place_id=fake-riverside-park/,
  );

  // Planning a meetup starts at the default court; picking another gives the meetup a Maps link.
  const meetups = page.getByRole("region", { name: "Meetups" });
  await meetups.getByRole("button", { name: "Plan one" }).click();
  const sheet = page.getByRole("dialog", { name: "Plan a meetup" });
  await expect(sheet.getByRole("radio", { name: "St James hall" })).toBeChecked();
  await sheet.getByText("Riverside courts", { exact: true }).click();
  await sheet.getByRole("button", { name: "Plan it" }).click();
  await expect(sheet).toBeHidden();
  await meetups.getByRole("article", { name: "Meetup at Riverside courts" }).getByRole("link").first().click();
  await expect(page).toHaveURL(/\/nights\//);
  await expect(page.getByRole("link", { name: /Open in Maps/ })).toHaveAttribute(
    "href",
    /query_place_id=fake-riverside-park/,
  );

  // Removing a court leaves the other.
  await page.goto(`${groupUrl}/settings`);
  await courts.getByRole("button", { name: "Remove Riverside courts" }).click();
  await expect(courts.getByRole("status")).toHaveText("Removed.");
  await expect(saved.getByRole("listitem")).toHaveCount(1);

  expect(problems).toEqual([]);
});

test("a meetup can still be somewhere else", async ({ page }) => {
  const lead = newUser("Ola");
  const crewId = await crew(page, lead, false);
  await apiAs(page, "POST", `/v1/groups/${crewId}/courts`, { label: "Hall" });
  await page.goto(`/groups/${crewId}`);
  const meetups = page.getByRole("region", { name: "Meetups" });
  await meetups.getByRole("button", { name: "Plan one" }).click();
  const sheet = page.getByRole("dialog", { name: "Plan a meetup" });
  await sheet.getByText("Somewhere else", { exact: true }).click();
  await sheet.getByLabel("Other venue").fill("Beach courts");
  await sheet.getByRole("button", { name: "Plan it" }).click();
  await expect(sheet).toBeHidden();
  await expect(meetups.getByRole("article", { name: "Meetup at Beach courts" })).toBeVisible();
});

test("without court search, courts are typed, and five is the most", async ({ page }) => {
  const crewId = await crew(page, newUser("Pim"), false);
  await page.goto(`/groups/${crewId}/settings`);
  const courts = page.getByRole("region", { name: "Courts" });
  await expect(courts.getByRole("button", { name: "Find on the map" })).toHaveCount(0);
  await courts.getByRole("button", { name: "Add a court" }).click();
  await courts.getByLabel("Court name").fill("See www.example.com");
  await courts.getByRole("button", { name: "Save court" }).click();
  await expect(courts.getByRole("status")).toHaveText("Leave out links and web or email addresses.");

  for (const label of ["A", "B", "C", "D", "E"]) {
    await apiAs(page, "POST", `/v1/groups/${crewId}/courts`, { label });
  }
  await page.reload();
  await expect(courts.getByRole("list", { name: "Saved courts" }).getByRole("listitem")).toHaveCount(5);
  await expect(courts.getByText("A crew can save up to 5 courts.")).toBeVisible();
  await expect(courts.getByRole("button", { name: "Add a court" })).toHaveCount(0);
});
