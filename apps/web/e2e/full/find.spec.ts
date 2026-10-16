import { expect, test, type Page } from "@playwright/test";

import { apiAs } from "./api";
import { newUser, signIn, type TestUser } from "./auth";
import { watchProblems } from "./problems";

// dev/run.sh makes this address the admin, and runs the API with made-up places (FakePlaces):
// Riverside Park is at 40.80, -73.97.
const ADMIN: TestUser = { name: "Admin Test", email: "admin@popshot.test" };
const RIVERSIDE = { latitude: 40.8, longitude: -73.97 };

/** A crew led by `lead`, with court search and open crews switched on and Riverside Park
 *  saved as its default court. Returns its id and name. */
async function crewAtRiverside(page: Page, lead: TestUser): Promise<{ id: string; name: string }> {
  await signIn(page, lead);
  await page.goto("/");
  const name = `Open ${String(Date.now()).slice(-6)}`;
  const crew = (await apiAs(page, "POST", "/v1/groups", { name })) as { id: string };
  await signIn(page, ADMIN);
  await page.goto("/");
  for (const key of ["courts.places", "crew.open"]) {
    await apiAs(page, "POST", `/v1/admin/features/crews/${crew.id}`, {
      key,
      reason: "Browser test: open crews for this crew.",
    });
  }
  await signIn(page, lead);
  await page.goto("/");
  await apiAs(page, "POST", `/v1/groups/${crew.id}/courts`, {
    label: "Riverside courts",
    place_id: "fake-riverside-park",
  });
  return { id: crew.id, name };
}

test("a lead opens a crew, and someone with no crew finds it near them and joins", async ({ page }) => {
  const lead = newUser("Rio");
  const crew = await crewAtRiverside(page, lead);

  // The lead opens it from settings, with room for 8.
  await page.goto(`/groups/${crew.id}/settings`);
  const section = page.getByRole("region", { name: "Open crew" });
  await expect(section).toContainText("Members, games and stats stay for members.");
  await section.getByRole("switch", { name: "Open to anyone on Popshot" }).check();
  await section.getByLabel("Players who can join from the listing").fill("8");
  await section.getByRole("button", { name: "Save" }).click();
  await expect(section.getByRole("status")).toHaveText("Saved.");

  // Someone new, with no crew: Find shows, and their location finds the crew.
  const ola = newUser("Ola");
  await page.context().grantPermissions(["geolocation"]);
  await page.context().setGeolocation(RIVERSIDE);
  await signIn(page, ola);
  const problems = await watchProblems(page);
  await page.goto("/");
  await page.getByRole("link", { name: "Find" }).first().click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Find");
  await page.getByRole("button", { name: "Use my location" }).click();
  const card = page.getByRole("article", { name: crew.name });
  await expect(card).toContainText("Plays at Riverside courts");
  await expect(card).toContainText("1 of 8 players");
  await expect(card).toContainText("Under 1 km");
  // Never who's in it.
  await expect(card).not.toContainText(lead.name);
  await expect(card.getByRole("link", { name: "Open Riverside courts in Maps" })).toHaveAttribute(
    "rel",
    "noopener noreferrer",
  );

  // Join: what members will see, then straight into the crew.
  await card.getByRole("button", { name: "Join" }).click();
  const sheet = page.getByRole("dialog", { name: `Join ${crew.name}?` });
  await expect(sheet).toContainText("Members see your name and photo");
  await sheet.getByRole("button", { name: "Join crew" }).click();
  await expect(page).toHaveURL(new RegExp(`/groups/${crew.id}$`));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(crew.name);

  // Back on Find, the same search runs again from this device, and the card says you're in.
  await page.goto("/find");
  await expect(page.getByText("Near you", { exact: true })).toBeVisible();
  await expect(card.getByRole("link", { name: /You're in/ })).toBeVisible();
  expect(problems).toEqual([]);

  // Close it again, so other tests' searches near Riverside aren't crowded.
  await signIn(page, lead);
  await page.goto("/");
  await apiAs(page, "PUT", `/v1/groups/${crew.id}/open`, { open: false, max_members: 8 });
});

test("without location, a typed park finds crews, is remembered, and a listing can be reported", async ({ page }) => {
  const lead = newUser("Sol");
  const crew = await crewAtRiverside(page, lead);
  await apiAs(page, "PUT", `/v1/groups/${crew.id}/open`, { open: true, max_members: 12 });

  const max = newUser("Max");
  // As when someone says no to sharing their location.
  await page.addInitScript(() => {
    navigator.geolocation.getCurrentPosition = (_ok, fail) => {
      fail?.({ code: 1, message: "denied", PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3 });
    };
  });
  await signIn(page, max);
  await page.goto("/find");
  await page.getByRole("button", { name: "Use my location" }).click();
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Search for a town or park instead.");

  await page.getByLabel("Or search for a town or park").fill("riverside");
  await page
    .getByRole("list", { name: "Places found" })
    .getByRole("button", { name: /Riverside Park Pickleball Courts/ })
    .click();
  const card = page.getByRole("article", { name: crew.name });
  await expect(card).toContainText("Plays at Riverside courts");
  await expect(card).toContainText("1 of 12 players");

  // Remembered on this device: the next visit searches from the same park.
  await page.reload();
  await expect(page.getByText("Near Riverside Park Pickleball Courts")).toBeVisible();
  await expect(card).toBeVisible();

  // Report: a reason, then thanks.
  await card.getByRole("button", { name: "Report" }).click();
  const report = page.getByRole("dialog", { name: `Report ${crew.name}` });
  await report.getByRole("button", { name: "Send report" }).click();
  await expect(report.getByRole("alert")).toHaveText("Pick a reason.");
  await report.getByLabel("Spam or advertising").check();
  await report.getByLabel("Anything to add? (optional)").fill("Posts ads for paddles.");
  await report.getByRole("button", { name: "Send report" }).click();
  await expect(report.getByRole("status")).toHaveText("Thanks. We'll look at it.");

  await signIn(page, lead);
  await page.goto("/");
  await apiAs(page, "PUT", `/v1/groups/${crew.id}/open`, { open: false, max_members: 12 });
});

test("a typed default court closes an open crew, and its lead is told why", async ({ page }) => {
  const lead = newUser("Pim");
  const crew = await crewAtRiverside(page, lead);
  await apiAs(page, "PUT", `/v1/groups/${crew.id}/open`, { open: true, max_members: 12 });
  const added = (await apiAs(page, "POST", `/v1/groups/${crew.id}/courts`, { label: "Hall" })) as {
    group: { courts: { id: string; label: string }[] };
  };
  const hall = added.group.courts.find((c) => c.label === "Hall");
  await apiAs(page, "PATCH", `/v1/groups/${crew.id}/courts/${hall?.id ?? ""}`, { is_default: true });

  await page.goto(`/groups/${crew.id}/settings`);
  const section = page.getByRole("region", { name: "Open crew" });
  await expect(section.getByRole("note")).toContainText("its default court isn't one from the map");
  const toggle = section.getByRole("switch", { name: "Open to anyone on Popshot" });
  await expect(toggle).not.toBeChecked();
  await expect(toggle).toBeDisabled();
  await expect(section).toContainText("Make a court from the map your default first");
});

test("without the open crews switch, settings have no Open crew section", async ({ page }) => {
  await signIn(page, newUser("Lou"));
  await page.goto("/");
  const crew = (await apiAs(page, "POST", "/v1/groups", { name: `Closed ${String(Date.now())}` })) as {
    id: string;
  };
  await page.goto(`/groups/${crew.id}/settings`);
  await expect(page.getByRole("region", { name: "Courts" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Open crew" })).toHaveCount(0);
});
