import { expect, test, type Page } from "@playwright/test";

import { newUser, signIn } from "./auth";
import { watchProblems } from "./problems";

async function logSingles(
  page: Page,
  groupUrl: string,
  me: string,
  guest: string,
  score: [string, string],
  isNew: boolean,
) {
  await page.goto(`${groupUrl}/log`);
  await page.getByRole("button", { name: "Change rules" }).click();
  await page.getByText("Singles", { exact: true }).click();
  await page.getByRole("button", { name: "Team B, player 1: pick a player" }).click();
  const picker = page.getByRole("dialog", { name: "Pick a player" });
  if (isNew) {
    await picker.getByRole("button", { name: "Add a guest" }).click();
    await page.getByRole("dialog", { name: "Add a guest" }).getByLabel("Guest's name").fill(guest);
    await page.getByRole("dialog", { name: "Add a guest" }).getByRole("button", { name: "Add guest" }).click();
  } else {
    await picker.getByRole("button", { name: new RegExp(`^${guest}`) }).click();
  }
  await expect(page.getByRole("dialog")).toBeHidden();
  await page.getByLabel(`Game 1, ${me}`).fill(score[0]);
  await page.getByLabel(`Game 1, ${guest}`).fill(score[1]);
  await page.getByRole("button", { name: "Log game" }).click();
  await expect(page).toHaveURL(/\/play$/);
}

test("your stats and the crew's highlights fill in as games are logged", async ({ page }) => {
  test.setTimeout(120_000);
  const user = newUser("Rio");
  await signIn(page, user);
  const problems = await watchProblems(page);

  await page.goto("/");
  await page.getByRole("button", { name: "Start a group" }).first().click();
  await page.getByLabel("Group name").fill("Rio's Crew");
  await page.getByRole("button", { name: "Create group" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Rio's Crew");
  const groupUrl = page.url();

  const stats = page.getByRole("region", { name: "Your stats" });
  await page.goto("/you");
  await expect(stats).toContainText("Your stats in Rio's Crew show up after your first game.");

  // A skunk, a close win, then a loss.
  await logSingles(page, groupUrl, user.name, "Lou", ["11", "2"], true);
  await logSingles(page, groupUrl, user.name, "Lou", ["12", "10"], false);
  await logSingles(page, groupUrl, user.name, "Lou", ["5", "11"], false);

  await page.goto("/you");
  await expect(stats).toContainText("3 games · 2–1 · Lost the last one");
  await expect(
    stats
      .getByRole("definition")
      .filter({ hasText: /^\d+–\d+$/ })
      .first(),
  ).toHaveText("1–0"); // close games
  await expect(stats).toContainText("No tough match-up yet.");
  await expect(stats.getByRole("list", { name: "Head to head" })).toContainText("Lou");
  await expect(stats.getByRole("list", { name: "Head to head" })).toContainText("2–1");

  // The dashboard: crew points over time, activity, and the window (30 days by default).
  await expect(stats.getByRole("radio", { name: "30 days" })).toBeChecked();
  await expect(stats.getByRole("img", { name: /^Crew points over 3 games/ })).toBeVisible();
  await expect(stats.getByLabel("Last 3, newest first: L W W")).toBeVisible();
  await expect(stats.getByRole("img", { name: /This week: 3\.$/ })).toBeVisible();
  await expect(stats).toContainText("Doubles · singles0 · 3");
  await stats.getByText("All time", { exact: true }).click();
  await expect(stats.getByRole("radio", { name: "All time" })).toBeChecked();
  await expect(stats).toContainText("all time");
  await expect(stats).toContainText("3 games · 2–1");

  // Home's short version.
  await page.goto("/");
  const home = page.getByRole("complementary", { name: "Your stats" });
  await expect(home).toContainText("Last 3");
  await expect(home).toContainText("2–1");
  await expect(home).toContainText("Last 7 days3 games");

  await page.goto("/crew");
  const highlights = page.getByRole("region", { name: /^Lately/ });
  await expect(highlights).toContainText("Longest win streak");
  await expect(highlights).toContainText("2 wins");
  await expect(highlights).toContainText(user.name);
  await expect(highlights).toContainText("3 games");
  // Both started this month (in either order: their first game was the same one).
  const welcome = highlights.getByRole("listitem").filter({ hasText: "Welcome to the crew" });
  await expect(welcome).toContainText("2 new");
  await expect(welcome).toContainText("Lou");
  await expect(welcome).toContainText(user.name);
  // Lou's upset stays on the You pages; the crew page doesn't name who lost.
  await expect(highlights).not.toContainText(`Lou beat ${user.name}`);
  expect(problems).toEqual([]);
});

test("you can compare how the last 30 days went in each crew", async ({ page }) => {
  test.setTimeout(180_000);
  const user = newUser("Noor");
  await signIn(page, user);
  const problems = await watchProblems(page);

  async function startGroup(name: string): Promise<string> {
    await page.goto("/");
    await page.getByRole("button", { name: "Start a group" }).first().click();
    await page.getByLabel("Group name").fill(name);
    await page.getByRole("button", { name: "Create group" }).click();
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(name);
    return page.url();
  }

  // Five easy wins in one crew, five heavy losses in the other.
  const thursday = await startGroup("Thursday Smashers");
  for (let i = 0; i < 5; i++) {
    await logSingles(page, thursday, user.name, "Lou", ["11", "2"], i === 0);
  }
  const sunday = await startGroup("Sunday Crew");
  for (let i = 0; i < 4; i++) {
    await logSingles(page, sunday, user.name, "Max", ["2", "11"], i === 0);
  }

  await page.goto("/you");
  const section = page.getByRole("region", { name: "Crew points" });
  // Four games isn't enough to call it, so nothing to compare yet.
  await expect(section).toContainText("4 games · a few more for a trend");
  await expect(section).not.toContainText("is where to focus");

  await logSingles(page, sunday, user.name, "Max", ["2", "11"], false);
  await page.goto("/you");
  await expect(section).toContainText("Going well in Thursday Smashers; Sunday Crew is where to focus.");
  const rows = section.getByRole("listitem");
  await expect(rows.filter({ hasText: "Thursday Smashers" })).toContainText("Climbing");
  await expect(rows.filter({ hasText: "Thursday Smashers" })).toContainText(
    /▲ \d\.\d\d in 30 days · 5 games · \d+% more of the points than expected/,
  );
  await expect(rows.filter({ hasText: "Sunday Crew" })).toContainText("Slipping");
  await expect(rows.filter({ hasText: "Sunday Crew" })).toContainText(
    /▼ \d\.\d\d in 30 days · 5 games · \d+% fewer of the points than expected/,
  );
  expect(problems).toEqual([]);
});
