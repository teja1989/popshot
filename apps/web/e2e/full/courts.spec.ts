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

/** A crew led by `lead`, with court search on when `places` is true. Returns its id. */
async function crew(page: Page, lead: TestUser, places: boolean): Promise<string> {
  await signIn(page, lead);
  await page.goto("/");
  const made = (await apiAs(page, "POST", "/v1/groups", { name: `Courts ${String(Date.now())}` })) as { id: string };
  if (places) {
    await setSwitch(page, made.id, lead, true);
  }
  return made.id;
}

test("a lead finds the crew's court on the map, names it, and members get a Maps link", async ({ page }) => {
  const lead = newUser("Rio");
  const crewId = await crew(page, lead, true);
  const groupUrl = `/groups/${crewId}`;
  const problems = await watchProblems(page);

  await page.goto(`${groupUrl}/settings`);
  const court = page.getByRole("region", { name: "Court on the map" });
  await court.getByLabel("Search for your court").fill("park");
  const found = court.getByRole("list", { name: "Courts found" });
  await expect(found.getByRole("button")).toHaveCount(2);
  await expect(court.getByText("Results from Google Maps")).toBeVisible();

  // Pick one: Google's name shows, but the crew names it in its own words.
  await found.getByRole("button", { name: /Riverside Park Pickleball Courts/ }).click();
  const name = court.getByLabel("What does your crew call it?");
  await expect(name).toBeFocused();
  await expect(name).toHaveValue("");
  await expect(court.getByRole("button", { name: "Save court" })).toBeDisabled();
  await name.fill("Riverside courts");
  await court.getByRole("button", { name: "Save court" }).click();
  await expect(court.getByRole("status")).toHaveText("Saved.");
  await expect(court.getByText("Riverside courts", { exact: true })).toBeVisible();

  const maps = court.getByRole("link", { name: /Open in Maps/ });
  await expect(maps).toHaveAttribute("target", "_blank");
  await expect(maps).toHaveAttribute("rel", "noopener noreferrer");
  const href = new URL((await maps.getAttribute("href")) ?? "");
  expect(href.origin + href.pathname).toBe("https://www.google.com/maps/search/");
  expect(href.searchParams.get("query_place_id")).toBe("fake-riverside-park");

  // The crew page shows it to members.
  await page.goto(groupUrl);
  await expect(page.getByText("Home court: Riverside courts")).toBeVisible();
  await expect(page.getByRole("link", { name: /Open in Maps/ })).toHaveAttribute(
    "href",
    /query_place_id=fake-riverside-park/,
  );

  // Changing your mind keeps the court; removing it clears the crew page.
  await page.goto(`${groupUrl}/settings`);
  await court.getByRole("button", { name: "Change" }).click();
  await court.getByRole("button", { name: "Keep Riverside courts" }).click();
  await court.getByRole("button", { name: "Remove" }).click();
  await expect(court.getByRole("status")).toHaveText("Removed.");
  await expect(court.getByLabel("Search for your court")).toBeVisible();
  await page.goto(groupUrl);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText(/^Home court:/)).toHaveCount(0);

  expect(problems).toEqual([]);
});

test("with the switch turned off, a saved court is hidden again", async ({ page }) => {
  const lead = newUser("Sol");
  const crewId = await crew(page, lead, true);
  await page.goto(`/groups/${crewId}/settings`);
  const court = page.getByRole("region", { name: "Court on the map" });
  await court.getByLabel("Search for your court").fill("sunset");
  await court.getByRole("button", { name: /Sunset Park Courts/ }).click();
  await court.getByLabel("What does your crew call it?").fill("Sunset courts");
  await court.getByRole("button", { name: "Save court" }).click();
  await expect(court.getByRole("status")).toHaveText("Saved.");

  await setSwitch(page, crewId, lead, false);
  await page.goto(`/groups/${crewId}`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByText(/^Home court:/)).toHaveCount(0);
  await page.goto(`/groups/${crewId}/settings`);
  await expect(page.getByRole("region", { name: "Crew profile" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Court on the map" })).toHaveCount(0);
});

test("nothing found, and a name with a link, are explained", async ({ page }) => {
  const crewId = await crew(page, newUser("Ola"), true);
  await page.goto(`/groups/${crewId}/settings`);
  const court = page.getByRole("region", { name: "Court on the map" });
  await court.getByLabel("Search for your court").fill("zzqx");
  await expect(court.getByText("Nothing found. Try another name.")).toBeVisible();

  await court.getByLabel("Search for your court").fill("sunset");
  await court.getByRole("button", { name: /Sunset Park Courts/ }).click();
  await court.getByLabel("What does your crew call it?").fill("see www.example.com");
  await court.getByRole("button", { name: "Save court" }).click();
  await expect(court.getByRole("status")).toHaveText("Leave out links and web or email addresses.");
});

test("without the switch, there's no court search", async ({ page }) => {
  const crewId = await crew(page, newUser("Pim"), false);
  await page.goto(`/groups/${crewId}/settings`);
  await expect(page.getByRole("region", { name: "Crew profile" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Court on the map" })).toHaveCount(0);
});
