import { expect, test } from "@playwright/test";

import { newUser, signIn } from "./auth";
import { watchProblems } from "./problems";

test("the You page offers notifications, and the service worker is served", async ({ page }) => {
  await signIn(page, newUser("Noa"));
  const problems = await watchProblems(page);
  await page.goto("/you/settings");
  const section = page.getByRole("region", { name: "Notifications" });
  await expect(section.getByRole("button", { name: "Turn on notifications" })).toBeVisible();

  const worker = await page.request.get("/sw.js");
  expect(worker.status()).toBe(200);
  expect(worker.headers()["content-type"]).toContain("text/javascript");
  expect(await worker.text()).toContain('addEventListener("push"');
  expect(problems).toEqual([]);
});

test("the install banner offers the browser's install dialog, and Not now sticks", async ({ page }) => {
  await signIn(page, newUser("Ivo"));
  const problems = await watchProblems(page);
  await page.goto("/");
  await page.getByRole("button", { name: "Start a group" }).first().click();
  await page.getByLabel("Group name").fill("Ivo's Crew");
  await page.getByRole("button", { name: "Create group" }).click();
  await expect(page).toHaveURL(/\/groups\//);

  // What Chrome fires when the app can be installed (headless browsers never do).
  const fireInstallPrompt = () =>
    page.evaluate(() => {
      const event = new Event("beforeinstallprompt") as Event & Record<string, unknown>;
      event.prompt = () => {
        (window as unknown as Record<string, boolean>).prompted = true;
        return Promise.resolve();
      };
      event.userChoice = Promise.resolve({ outcome: "dismissed" });
      window.dispatchEvent(event);
    });

  await page.goto("/");
  const banner = page.getByRole("region", { name: "Put Popshot on your home screen" });
  await expect(banner).toHaveCount(0);
  await fireInstallPrompt();
  await expect(banner).toBeVisible();
  await banner.getByRole("button", { name: "Install" }).click();
  await expect.poll(() => page.evaluate(() => (window as unknown as Record<string, boolean>).prompted)).toBe(true);
  // They dismissed the browser's dialog: the event is used up, so the banner goes.
  await expect(banner).toHaveCount(0);

  await page.reload();
  await fireInstallPrompt();
  await banner.getByRole("button", { name: "Not now" }).click();
  await expect(banner).toHaveCount(0);
  await page.reload();
  await fireInstallPrompt();
  await expect(banner).toHaveCount(0);
  expect(problems).toEqual([]);
});
