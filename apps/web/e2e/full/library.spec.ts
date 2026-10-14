import { expect, test } from "@playwright/test";

import { apiAs } from "./api";
import { newUser, signIn, type TestUser } from "./auth";
import { watchProblems } from "./problems";

// The content library: an admin adds and publishes a video; a player whose journey is on sees
// it on the Journey tab, for the skill they're working on; unpublished, it's gone.

// dev/run.sh makes this address the admin.
const ADMIN: TestUser = { name: "Admin Test", email: "admin@popshot.test" };
const REASON = "Browser test: a clear video for this skill.";

// Phone and desktop run side by side, so each uses its own skill: the day's pick is one of
// the skill's published items, and the other run's video mustn't be the one shown.
const SKILL = {
  mobile: { id: "staying_calm", label: "Staying calm after errors", tip: /slow breath|resetting/ },
  chromium: { id: "dinking_patience", label: "Dinking patience", tip: /Count your dinks|Dink to space/ },
};

test("an admin publishes a video and a player sees it on Journey", async ({ page }, testInfo) => {
  test.setTimeout(90_000);
  const skill = testInfo.project.name === "mobile" ? SKILL.mobile : SKILL.chromium;
  // A unique video per run and project, so runs don't collide on the same link.
  const id = `${String(Date.now()).slice(-6)}${String(Math.floor(Math.random() * 1e5)).padStart(5, "0")}`;
  const title = `Calm dinks ${id}`;
  const player = newUser("Sol");

  // The player: a crew with the journey on, and a story about dinking.
  await signIn(page, player);
  await page.goto("/");
  const crew = (await apiAs(page, "POST", "/v1/groups", { name: `Library ${id}` })) as { id: string };

  await signIn(page, ADMIN);
  await page.goto("/");
  await apiAs(page, "POST", `/v1/admin/features/crews/${crew.id}`, { key: "you.journey", reason: REASON });
  const problems = await watchProblems(page);

  // Add it through the Library page.
  await page.goto("/admin/library");
  await expect(page.getByRole("heading", { level: 1, name: "Library" })).toBeVisible();
  await page.getByRole("button", { name: "Add an item" }).click();
  const sheet = page.getByRole("dialog", { name: "Add to the library" });
  await sheet.getByRole("textbox", { name: "Link" }).fill(`https://youtu.be/${id}?si=share`);
  await sheet.getByRole("textbox", { name: "Title" }).fill(title);
  await sheet.getByRole("textbox", { name: "Channel or site" }).fill("A Coach");
  await sheet.getByRole("textbox", { name: "Minutes (optional)" }).fill("6");
  await sheet.getByRole("button", { name: skill.label }).click();
  await sheet.getByRole("textbox", { name: "Why" }).fill(REASON);
  await sheet.getByRole("button", { name: "Add as a draft" }).click();
  await expect(sheet).toHaveCount(0);
  const card = page.getByRole("listitem").filter({ hasText: title });
  await expect(card.getByText("Draft", { exact: true })).toBeVisible();
  // Stored in one tidy form.
  await expect(card.getByRole("link", { name: `https://www.youtube.com/watch?v=${id}` })).toBeVisible();

  await card.getByRole("button", { name: `Publish ${title}` }).click();
  const publish = page.getByRole("dialog", { name: "Publish this item" });
  await publish.getByRole("textbox", { name: "Why" }).fill(REASON);
  await publish.getByRole("button", { name: "Publish" }).click();
  await expect(card.getByText("Published", { exact: true })).toBeVisible();
  expect(problems).toEqual([]);

  // The player sees it with today's tip.
  await signIn(page, player);
  await page.goto("/");
  await apiAs(page, "PUT", "/v1/me/journey/story", {
    gaps: "I rush when it gets tense.",
    tag_strengths: [],
    tag_gaps: [skill.id],
  });
  await page.goto("/you/journey");
  const today = page.getByRole("region", { name: "Today's one thing" });
  const link = today.getByRole("link", { name: new RegExp(title) });
  await expect(link).toBeVisible();
  await expect(link).toHaveAttribute("href", `https://www.youtube.com/watch?v=${id}`);
  await expect(link).toHaveAttribute("target", "_blank");
  await expect(link).toHaveAttribute("rel", "noopener noreferrer");
  await expect(link).toContainText("Watch · 6 min");

  // Unpublished, it's gone.
  await signIn(page, ADMIN);
  await page.goto("/admin/library");
  await page.getByRole("button", { name: `Unpublish ${title}` }).click();
  const unpublish = page.getByRole("dialog", { name: "Unpublish this item" });
  await unpublish.getByRole("textbox", { name: "Why" }).fill(REASON);
  await unpublish.getByRole("button", { name: "Unpublish" }).click();
  await expect(page.getByRole("listitem").filter({ hasText: title }).getByText("Draft", { exact: true })).toBeVisible();
  await signIn(page, player);
  await page.goto("/you/journey");
  await expect(today.getByText(skill.tip)).toBeVisible();
  await expect(today.getByRole("link")).toHaveCount(0);
});

test("the Library page is out of bounds for players", async ({ page }) => {
  await signIn(page, newUser("Tam"));
  await page.goto("/admin/library");
  await expect(page.getByRole("heading", { name: "That page is out of bounds." })).toBeVisible();
});
