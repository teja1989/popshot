import { expect, test, type Locator, type Page } from "@playwright/test";

import { newUser, signIn } from "./auth";
import { watchProblems } from "./problems";

async function addGuestTo(page: Page, slot: Locator, name: string): Promise<void> {
  await slot.click();
  await page.getByRole("dialog", { name: "Pick a player" }).getByRole("button", { name: "Add a guest" }).click();
  const guest = page.getByRole("dialog", { name: "Add a guest" });
  await guest.getByLabel("Guest's name").fill(name);
  await guest.getByRole("button", { name: "Add guest" }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
}

test("after a game, the Crew tab links to a recap with friendly awards", async ({ page }) => {
  const nora = newUser("Nora");
  await signIn(page, nora);
  const problems = await watchProblems(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Start a group" }).first().click();
  await page.getByLabel("Group name").fill("Lunch Dinkers");
  await page.getByRole("button", { name: "Create group" }).click();
  await expect(page).toHaveURL(/\/groups\/[0-9a-f-]{36}$/);
  const groupUrl = page.url();

  // No games, no recap.
  await page.goto("/crew");
  await expect(page.getByRole("heading", { name: "No games yet" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Latest outing" })).toHaveCount(0);

  // A doubles game won by two.
  await page.goto(`${groupUrl}/log`);
  await addGuestTo(page, page.getByRole("button", { name: "Team A, player 2: pick a player" }), "Ivy");
  await addGuestTo(page, page.getByRole("button", { name: "Team B, player 1: pick a player" }), "Raj");
  await addGuestTo(page, page.getByRole("button", { name: "Team B, player 2: pick a player" }), "Lena");
  await page.getByLabel(`Game 1, ${nora.name} & Ivy`).fill("11");
  await page.getByLabel("Game 1, Raj & Lena").fill("9");
  await page.getByRole("button", { name: "Log game" }).click();
  await expect(page).toHaveURL(/\/play/);
  await page.getByRole("dialog", { name: "How did it go?" }).getByRole("button", { name: "Skip this game" }).click();

  await page.goto("/crew");
  const latest = page.getByRole("region", { name: "Latest outing" });
  await expect(latest).toContainText("1 game · 4 players");
  await latest.getByRole("link", { name: /See the recap/ }).click();
  await expect(page).toHaveURL(/\/recaps\/[0-9a-f-]{36}$/);

  await expect(page.getByRole("heading", { level: 1 })).toContainText(/game/i);
  // Everyone's new, so everyone is welcomed.
  await expect(page.getByRole("main")).toContainText(/welcome/i);
  const awards = page.getByRole("region", { name: "Awards" });
  // Award winners are listed A to Z.
  await expect(awards.getByRole("listitem").filter({ hasText: "Close Call" })).toContainText(`Ivy, ${nora.name}`);
  await expect(page.getByRole("region", { name: "Who played" }).getByRole("listitem")).toHaveCount(4);
  const games = page.getByRole("region", { name: "The games" });
  const game = games.getByRole("listitem");
  await expect(game.locator("span").first()).toHaveText(/^(Ivy & Nora Test|Nora Test & Ivy)$/);
  await expect(game).toContainText(/11–9 · vs (Raj & Lena|Lena & Raj)/);
  // Popshot's own words here (the AI is off in tests), so no AI label.
  await expect(page.getByText("Written by AI", { exact: false })).toHaveCount(0);
  // Nothing about losing.
  await expect(page.getByRole("main")).not.toContainText(/\b(lost|beat|worst)\b/i);

  // A recap belongs to the Crew tab.
  await expect(page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "Crew" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await page.getByRole("link", { name: "Crew" }).first().click();
  await expect(page).toHaveURL(/\/crew$/);
  expect(problems).toEqual([]);
});

test("a recap you can't see is not found", async ({ page }) => {
  await signIn(page, newUser("Omar"));
  await page.goto("/groups/00000000-0000-4000-8000-000000000000/recaps/00000000-0000-4000-8000-000000000001");
  await expect(page.getByRole("heading", { name: "We couldn't find that recap." })).toBeVisible();
});

test("a shared recap opens for anyone, hides people who opt out, and can be turned off", async ({ page, browser }) => {
  const nora = newUser("Nora");
  await signIn(page, nora);
  const problems = await watchProblems(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Start a group" }).first().click();
  await page.getByLabel("Group name").fill("Lunch Dinkers");
  await page.getByRole("button", { name: "Create group" }).click();
  await expect(page).toHaveURL(/\/groups\/[0-9a-f-]{36}$/);
  await page.goto(`${page.url()}/log`);
  await addGuestTo(page, page.getByRole("button", { name: "Team A, player 2: pick a player" }), "Ivy");
  await addGuestTo(page, page.getByRole("button", { name: "Team B, player 1: pick a player" }), "Raj");
  await addGuestTo(page, page.getByRole("button", { name: "Team B, player 2: pick a player" }), "Lena");
  await page.getByLabel(`Game 1, ${nora.name} & Ivy`).fill("11");
  await page.getByLabel("Game 1, Raj & Lena").fill("9");
  await page.getByRole("button", { name: "Log game" }).click();
  await expect(page).toHaveURL(/\/play/);
  await page.getByRole("dialog", { name: "How did it go?" }).getByRole("button", { name: "Skip this game" }).click();
  await page.goto("/crew");
  await page
    .getByRole("region", { name: "Latest outing" })
    .getByRole("link", { name: /See the recap/ })
    .click();
  await expect(page).toHaveURL(/\/recaps\/[0-9a-f-]{36}$/);
  const recapUrl = page.url();

  const sharing = page.getByRole("region", { name: "Share this recap" });
  await sharing.getByRole("button", { name: "Share", exact: true }).click();
  const link = await sharing.getByLabel("Share link").inputValue();
  expect(link).toMatch(/\/r\/[A-Za-z0-9_-]{43}$/);
  const path = new URL(link).pathname;

  // Someone who isn't signed in.
  const stranger = await browser.newContext();
  const visitor = await stranger.newPage();
  const visitorProblems = await watchProblems(visitor);
  await visitor.goto(path);
  await expect(visitor.getByRole("heading", { level: 1 })).toContainText(/game/i);
  const card = visitor.getByRole("main");
  await expect(card).toContainText("Lunch Dinkers · 1 game · 4 players");
  await expect(card).toContainText("Keep score with your own crew.");
  await expect(visitor.getByRole("region", { name: "The games" })).toContainText(/11–9 · vs (Raj & Lena|Lena & Raj)/);
  await expect(visitor.getByRole("region", { name: "Who played" })).toContainText("Nora");
  // First names only.
  await expect(card).not.toContainText("Nora Test");
  // The chat preview: an image without names, and a description without names.
  const image = await visitor.locator('meta[property="og:image"]').getAttribute("content");
  expect(image).toBeTruthy();
  const imageUrl = new URL(image ?? "");
  const preview = await visitor.request.get(imageUrl.pathname + imageUrl.search);
  expect(preview.status()).toBe(200);
  expect(preview.headers()["content-type"]).toContain("image/png");
  await expect(visitor.locator('meta[property="og:description"]')).toHaveAttribute(
    "content",
    "1 game · 4 players with Lunch Dinkers.",
  );

  // Nora would rather not be named on shared cards.
  await page.goto("/you");
  const shared = page.getByRole("region", { name: "Shared recaps" });
  // Saved first, then the switch moves (like the notification switches).
  await shared.getByRole("switch", { name: /Show my first name/ }).click();
  await expect(shared.getByRole("switch", { name: /Show my first name/ })).not.toBeChecked();
  await visitor.reload();
  await expect(visitor.getByRole("region", { name: "Who played" })).toContainText("Crew member");
  await expect(visitor.getByRole("main")).not.toContainText("Nora");

  // Turning the link off.
  await page.goto(recapUrl);
  await page.getByRole("region", { name: "Share this recap" }).getByRole("button", { name: "Turn off links" }).click();
  await expect(page.getByRole("region", { name: "Share this recap" })).toContainText(
    "Links you can turn off are off now.",
  );
  const gone = await visitor.goto(path);
  expect(gone?.status()).toBe(404);
  await expect(visitor.getByRole("heading", { name: "This recap link isn't available any more." })).toBeVisible();

  await stranger.close();
  expect(problems).toEqual([]);
  expect(visitorProblems.filter((p) => !p.includes("404"))).toEqual([]);
});
