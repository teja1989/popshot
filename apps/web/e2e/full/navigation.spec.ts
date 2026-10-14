import { expect, test, type Page } from "@playwright/test";

import { newUser, signIn } from "./auth";
import { watchProblems } from "./problems";

function nav(page: Page) {
  // One of the two navs (sidebar or tab bar) is hidden at any width; this finds the visible one.
  return page.getByRole("navigation", { name: "Main" });
}

async function startGroup(page: Page, name: string): Promise<string> {
  await page.goto("/");
  await page.getByRole("button", { name: "Start a group" }).first().click();
  await page.getByLabel("Group name").fill(name);
  await page.getByRole("button", { name: "Create group" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(name);
  return page.url();
}

test("the tabs move between pages and show where you are", async ({ page }) => {
  const user = newUser("Nia");
  await signIn(page, user);
  const problems = await watchProblems(page);
  await page.goto("/");

  for (const [label, path, heading] of [
    ["Play", "/play", "Play"],
    ["Crew", "/crew", "Crew"],
    ["You", "/you", user.name],
    ["More", "/more", "More"],
    ["Home", "/", /^Good (morning|afternoon|evening), Nia\.$/],
  ] as const) {
    await nav(page).getByRole("link", { name: label }).click();
    await expect(page).toHaveURL(new RegExp(`${path}$`));
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(heading);
    await expect(nav(page).getByRole("link", { name: label })).toHaveAttribute("aria-current", "page");
  }
  expect(problems).toEqual([]);
});

test("Play and Crew follow the chosen group and remember it", async ({ page }) => {
  await signIn(page, newUser("Omar"));
  await startGroup(page, "Alpha Crew");
  await startGroup(page, "Beta Crew");

  await page.goto("/play");
  const group = page.getByLabel("Group");
  await expect(group).toHaveValue(/.+/);
  await group.selectOption({ label: "Beta Crew" });
  await expect(page.getByRole("heading", { name: "No games in Beta Crew yet" })).toBeVisible();

  // Remembered across pages and reloads on this device.
  await page.goto("/crew");
  await expect(page.getByLabel("Group")).toHaveValue(
    (await page.getByLabel("Group").locator("option", { hasText: "Beta Crew" }).getAttribute("value")) ?? "",
  );
  await page.reload();
  await expect(page.getByLabel("Group").locator("option:checked")).toHaveText("Beta Crew");
});

test("the Crew tab lists everyone A to Z, never ranked, with your own crew points", async ({ page }) => {
  const user = newUser("Pia");
  await signIn(page, user);
  const problems = await watchProblems(page);
  await page.goto("/crew");
  await expect(page.getByText("You're not in a group yet.", { exact: false })).toBeVisible();

  const groupUrl = await startGroup(page, "Pia's Crew");
  // Old links to the Board land on the Crew tab.
  await page.goto("/board");
  await expect(page).toHaveURL(/\/crew$/);
  await expect(page.getByRole("heading", { name: "No games yet" })).toBeVisible();
  const everyone = page.getByRole("list", { name: /Everyone/ });
  await expect(everyone).toContainText(`${user.name} (you)`);
  await expect(everyone).toContainText("0 games");
  await expect(page.getByRole("region", { name: "Your crew points" })).toHaveCount(0);

  // One win against a guest.
  await page.goto(`${groupUrl}/log`);
  await page.getByRole("button", { name: "Change rules" }).click();
  await page.getByText("Singles", { exact: true }).click();
  await page.getByRole("button", { name: "Team B, player 1: pick a player" }).click();
  await page.getByRole("dialog", { name: "Pick a player" }).getByRole("button", { name: "Add a guest" }).click();
  await page.getByRole("dialog", { name: "Add a guest" }).getByLabel("Guest's name").fill("Lou");
  await page.getByRole("dialog", { name: "Add a guest" }).getByRole("button", { name: "Add guest" }).click();
  await page.getByLabel(`Game 1, ${user.name}`).fill("11");
  await page.getByLabel("Game 1, Lou").fill("3");
  await page.getByRole("button", { name: "Log game" }).click();
  await expect(page).toHaveURL(/\/play$/);

  await page.goto("/crew");
  // A to Z with game counts; no ranks anywhere. (Each row starts with the avatar's initials.)
  await expect(everyone.getByRole("listitem")).toHaveText([
    /Lou · guest\s*1 game$/,
    new RegExp(`${user.name} \\(you\\)\\s*1 game$`),
  ]);
  await expect(page.getByRole("heading", { name: /[Rr]anked/ })).toHaveCount(0);
  // Your own crew points, still settling.
  const mine = page.getByRole("region", { name: "Your crew points" });
  const points = Number(await mine.getByText(/^\d\.\d\d$/).textContent());
  expect(points).toBeGreaterThan(3);
  expect(points).toBeLessThanOrEqual(6);
  await expect(mine).toContainText("Still settling: 9 more games");
  await mine.getByRole("button", { name: "How crew points work" }).click();
  await expect(page.getByRole("dialog", { name: "How crew points work" })).toContainText("doesn't rank your crew");
  expect(problems).toEqual([]);
});

test("the ⓘ explains crew points and how they differ from your level", async ({ page }) => {
  await signIn(page, newUser("Ines"));
  const problems = await watchProblems(page);
  await startGroup(page, "Ines's Crew");
  for (const path of ["/you"]) {
    await page.goto(path);
    await page.getByRole("button", { name: "How crew points work" }).first().click();
    const sheet = page.getByRole("dialog", { name: "How crew points work" });
    await expect(sheet).toContainText("Your level vs. your crew points");
    await expect(sheet).toContainText("only where your crew points start");
    await expect(sheet).toContainText("+0.03");
    await expect(sheet).toContainText("Advanced · 4.00");
    await page.keyboard.press("Escape");
    await expect(sheet).toBeHidden();
  }
  expect(problems).toEqual([]);
});

test("your level sets where crew points start", async ({ page }) => {
  await signIn(page, newUser("Kai"));
  await page.goto("/you");
  const section = page.getByRole("region", { name: "Crew points" });
  await expect(section).toContainText("Your crew points show up after your first game.");
  await expect(section.getByRole("radio", { name: /Not set/ })).toBeChecked();
  await section.getByRole("radio", { name: /Advanced/ }).check();
  await page.reload();
  await expect(
    page.getByRole("region", { name: "Crew points" }).getByRole("radio", { name: /Advanced/ }),
  ).toBeChecked();
});

test("appearance is remembered and applied before the page paints", async ({ page }) => {
  await signIn(page, newUser("Quinn"));
  const problems = await watchProblems(page);
  await page.goto("/you");
  const theme = () => page.evaluate(() => document.documentElement.dataset.theme ?? "system");

  await page.getByText("Dark", { exact: true }).click();
  expect(await theme()).toBe("dark");

  // After a reload, the inline script (carrying the CSP nonce) sets it before any app code.
  await page.reload({ waitUntil: "commit" });
  await page.waitForFunction(() => document.documentElement.dataset.theme !== undefined);
  expect(await theme()).toBe("dark");
  await expect(page.getByRole("radio", { name: "Dark" })).toBeChecked();

  await page.getByText("Match device", { exact: true }).click();
  expect(await theme()).toBe("system");
  await page.reload();
  await expect(page.getByRole("radio", { name: "Match device" })).toBeChecked();
  expect(await theme()).toBe("system");
  expect(problems).toEqual([]);
});

test("on Home, the logo and the Home tab scroll to the top, or refresh at the top", async ({ page, context }) => {
  await signIn(page, newUser("Ola"));
  const problems = await watchProblems(page);
  await startGroup(page, "First Crew");
  await page.goto("/");
  await expect(page.getByRole("link", { name: /First Crew/ })).toBeVisible();

  // A crew made elsewhere (another tab) shows up when you tap the logo at the top of Home.
  const other = await context.newPage();
  await startGroup(other, "Second Crew");
  await other.close();
  await expect(page.getByRole("link", { name: /Second Crew/ })).toHaveCount(0);
  await page.getByRole("link", { name: "Popshot home" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("link", { name: /Second Crew/ })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "Updated." })).toBeVisible();
  await expect(page.getByRole("status").filter({ hasText: "Updated." })).toHaveCount(0, { timeout: 8000 });

  // Scrolled down, the Home tab brings you back up (when the page is long enough to scroll).
  await page.evaluate(() => {
    window.scrollTo(0, document.body.scrollHeight);
  });
  if ((await page.evaluate(() => window.scrollY)) > 0) {
    await nav(page).getByRole("link", { name: "Home" }).click();
    await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0);
    await expect(page).toHaveURL(/\/$/);
  }
  expect(problems).toEqual([]);
});

test("Play shows the crew's meetups first, and old Games links still work", async ({ page }) => {
  await signIn(page, newUser("Ivo"));
  const problems = await watchProblems(page);
  await startGroup(page, "Ivo's Crew");

  // An old link (from a notification, say) lands on Play with its message intact.
  await page.goto("/games?logged=1");
  await expect(page).toHaveURL(/\/play$/);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Play");
  await expect(page.getByRole("status").filter({ hasText: "Game logged." })).toBeVisible();

  // Meetups come first, and one can be planned from here.
  const meetups = page.getByRole("region", { name: "Meetups" });
  await expect(meetups).toContainText("Nothing planned yet.");
  await expect(meetups.getByRole("button", { name: "Plan one" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Log a game" })).toBeVisible();
  expect(problems).toEqual([]);
});

test("a tab behind a feature switch comes and goes without a reload", async ({ page }) => {
  await signIn(page, newUser("Ivo"));
  // The real answer first: the five tabs, with nothing extra switched on.
  const real = page.waitForResponse((r) => r.url().endsWith("/api/v1/me/features"));
  await page.goto("/");
  expect((await real).status()).toBe(200);
  await expect(nav(page).getByRole("link")).toHaveText(["Home", "Play", "Crew", "You", "More"]);

  // Stand in for an admin switching Learn on, then off again.
  let on = ["learn.tab"];
  await page.route("**/api/v1/me/features", (route) =>
    route.fulfill({ contentType: "application/json", body: JSON.stringify({ crews: {}, everywhere: on }) }),
  );
  const comeBack = () => page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")));
  await comeBack();
  await expect(nav(page).getByRole("link")).toHaveText(["Home", "Play", "Crew", "Learn", "You", "More"]);
  on = [];
  await comeBack();
  await expect(nav(page).getByRole("link")).toHaveText(["Home", "Play", "Crew", "You", "More"]);
});
