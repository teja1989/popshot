import { expect, test, type Page } from "@playwright/test";

import { apiAs } from "./api";
import { newUser, signIn, type TestUser } from "./auth";
import { watchProblems } from "./problems";

// dev/run.sh makes this address the admin.
const ADMIN: TestUser = { name: "Admin Test", email: "admin@popshot.test" };
const REASON = "Browser test for the Learn preview.";

// A serve, a return and a third-shot drop, as in the API's tests.
function scene(dropApex = 7) {
  return {
    schema_version: 1,
    duration: 6,
    camera: "behind",
    actors: [
      {
        id: "you",
        keys: [
          { t: 0, x: 15, y: 1 },
          { t: 3.6, x: 14, y: 3 },
          { t: 6, x: 13, y: 12, stance: "split" },
        ],
      },
      { id: "partner", keys: [{ t: 0, x: 5, y: 1 }] },
      {
        id: "them_1",
        keys: [
          { t: 0, x: 5, y: 41 },
          { t: 3, x: 6, y: 30 },
        ],
      },
      { id: "them_2", keys: [{ t: 0, x: 15, y: 30 }] },
    ],
    flights: [
      { t0: 0, t1: 1.2, start: { x: 15, y: 1, z: 2.5 }, end: { x: 5, y: 38, z: 0 }, apex_z: 8, kind: "serve" },
      { t0: 1.8, t1: 3, start: { x: 5, y: 40, z: 1.5 }, end: { x: 14, y: 4, z: 0 }, apex_z: 9, kind: "return" },
      {
        t0: 3.6,
        t1: 5,
        start: { x: 14, y: 3, z: 1.5 },
        end: { x: 8, y: 25, z: 0 },
        apex_z: dropApex,
        kind: "drop",
      },
    ],
    callouts: [{ t: 0.2, text: "Serve deep" }],
    zones: [],
  };
}

async function createShot(page: Page, title: string, dropApex = 7): Promise<string> {
  const made = (await apiAs(page, "POST", "/v1/admin/learn/shots", {
    slug: `e2e-${String(Date.now())}-${String(Math.floor(Math.random() * 1000))}`,
    title,
    summary: "Take the net back with a soft shot.",
    level: "intermediate",
    focus_ids: ["third_shot_drop"],
    tips: ["Lift from low to high."],
    drill_steps: ["Ten drops cross-court."],
    scene: scene(dropApex),
    reason: REASON,
  })) as { id: string };
  return made.id;
}

test("Learn shots are 'not found' for everyone but admins", async ({ page }) => {
  await signIn(page, newUser("Casey"));
  await page.goto("/admin/learn");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("That page is out of bounds.");
});

test("the admin previews a shot, plays it from the keyboard and views it from above", async ({ page }) => {
  const problems = await watchProblems(page);
  await signIn(page, ADMIN);
  const title = `Drop ${String(Date.now())}`;
  await page.goto("/admin");
  await createShot(page, title);

  await page.getByRole("link", { name: "Learn shots →" }).click();
  const row = page.getByRole("link").filter({ hasText: title });
  await expect(row).toContainText("Draft");
  await row.click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(title);
  await expect(page.getByText("Fix these before publishing:")).toHaveCount(0);
  await expect(page.getByText("Third-shot drops")).toBeVisible();
  await expect(page.getByText("Ten drops cross-court.")).toBeVisible();

  // Nothing plays until asked. Then it runs, from the keyboard alone.
  const timeline = page.getByRole("slider", { name: "Time" });
  await expect(timeline).toHaveAttribute("aria-valuetext", "0:00.0");
  await page.getByRole("button", { name: "Play" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByText("Serve deep")).toBeVisible();
  await expect(timeline).not.toHaveAttribute("aria-valuetext", "0:00.0");
  await page.getByRole("button", { name: "Pause" }).press("Enter");
  await timeline.focus();
  await page.keyboard.press("End");
  await expect(timeline).toHaveAttribute("aria-valuetext", "0:06.0");
  await expect(page.getByRole("button", { name: "Play again" })).toBeVisible();

  // 3D where the browser can draw it; from above either way.
  const above = page.getByRole("radio", { name: "From above" });
  if ((await above.count()) > 0) {
    await expect(
      page.getByRole("img", { name: `${title}, in 3D. Shots in order: Serve, Return, Drop.` }),
    ).toBeVisible();
    await page.getByText("From above").click();
  }
  await expect(page.getByRole("img", { name: "Court from above. Shots in order: Serve, Return, Drop." })).toBeVisible();
  expect(problems).toEqual([]);
});

test("a shot that hits the net says what to fix", async ({ page }) => {
  await signIn(page, ADMIN);
  await page.goto("/admin");
  const id = await createShot(page, `Into the net ${String(Date.now())}`, 1.5);
  await page.goto(`/admin/learn/${id}`);
  await expect(page.getByRole("status")).toContainText("Fix these before publishing:");
  await expect(page.getByRole("status")).toContainText("Shot 3 hits the net.");
});

test("with reduced motion it opens from above", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await signIn(page, ADMIN);
  await page.goto("/admin");
  const id = await createShot(page, `Calm ${String(Date.now())}`);
  await page.goto(`/admin/learn/${id}`);
  await expect(page.getByRole("img", { name: "Court from above. Shots in order: Serve, Return, Drop." })).toBeVisible();
  await expect(page.getByRole("img", { name: /in 3D/ })).toHaveCount(0);
});
