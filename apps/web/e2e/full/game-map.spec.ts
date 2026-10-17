import { expect, test, type Page } from "@playwright/test";

import { apiAs, logSinglesAs } from "./api";
import { newUser, signIn, type TestUser } from "./auth";
import { watchProblems } from "./problems";

// dev/run.sh makes this address the admin.
const ADMIN: TestUser = { name: "Admin Test", email: "admin@popshot.test" };

/** A crew led by `lead`, with guest Gary, and the game map switched on for it. */
async function crewWithMap(page: Page, lead: TestUser): Promise<string> {
  await signIn(page, lead);
  await page.goto("/");
  const crew = (await apiAs(page, "POST", "/v1/groups", { name: `Map ${String(Date.now()).slice(-6)}` })) as {
    id: string;
  };
  await apiAs(page, "POST", `/v1/groups/${crew.id}/players`, { display_name: "Gary" });
  await signIn(page, ADMIN);
  await page.goto("/");
  await apiAs(page, "POST", `/v1/admin/features/crews/${crew.id}`, {
    key: "you.map",
    reason: "Browser test: the game map for this crew.",
  });
  await signIn(page, lead);
  await page.goto("/");
  return crew.id;
}

test("your game map shows where your game is, with a next step and your own goal", async ({ page }) => {
  const nora = newUser("Nora");
  const crewId = await crewWithMap(page, nora);
  for (let i = 0; i < 5; i++) {
    await logSinglesAs(page, crewId, "Gary", [11, 2]);
  }
  const problems = await watchProblems(page);
  await page.goto("/you");
  const map = page.getByRole("region", { name: "Your game map" });
  await expect(map).toContainText("Only you see it.");
  // Five big wins in four weeks: results ahead, fewer games than the goal of 2.
  await expect(map.getByText("Sharp, play more", { exact: true }).last()).toBeVisible();
  await expect(map.getByRole("link", { name: "Find a meetup this week" })).toHaveAttribute("href", "/play");
  await expect(map.getByRole("group")).toHaveAccessibleName(/^Sharp, play more: 1\.3 games a week/);

  // The dot tells you about its week, by keyboard too.
  const now = map.getByRole("img", { name: /^Week to/ });
  await now.focus();
  await expect(page.getByRole("tooltip")).toContainText("games a week");

  // The same weeks as a table.
  await map.getByRole("button", { name: "Show as a table" }).click();
  await expect(map.getByRole("table").getByRole("row")).toHaveCount(7);
  await map.getByRole("button", { name: "Show the map" }).click();

  // A goal of 1 a week: now that's playing often.
  await map.getByRole("button", { name: "Goal: 2 games a week" }).click();
  const sheet = page.getByRole("dialog", { name: "Your weekly goal" });
  await sheet.getByLabel("Games a week").selectOption("1");
  await sheet.getByRole("button", { name: "Save goal" }).click();
  await expect(sheet).toBeHidden();
  await expect(map.getByRole("button", { name: "Goal: 1 game a week" })).toBeVisible();
  await expect(map.getByRole("link", { name: "Share a recap with friends" })).toBeVisible();
  expect(problems).toEqual([]);
});

test("a new player sees what the map needs", async ({ page }) => {
  const ola = newUser("Ola");
  await crewWithMap(page, ola);
  await page.goto("/you");
  const map = page.getByRole("region", { name: "Your game map" });
  await expect(map).toContainText("A few more games and your map appears. It needs 5 games in 28 days.");
});

test("without the switch there's no map", async ({ page }) => {
  await signIn(page, newUser("Lou"));
  await page.goto("/you");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("region", { name: "Your game map" })).toHaveCount(0);
});
