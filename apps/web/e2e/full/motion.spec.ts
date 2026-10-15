import { expect, test } from "@playwright/test";

import { newUser, signIn } from "./auth";

// On phones, a slim bar with the page's title slides in once its big title scrolls away.

test("the compact title bar follows the page title on phones", async ({ page, isMobile }) => {
  await signIn(page, newUser("Ivy"));
  await page.goto("/you/settings");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Settings");
  await expect(page.getByRole("heading", { name: "Your data" })).toBeVisible();
  const bar = page.locator("[data-compact-title]");
  if (!isMobile) {
    await expect(bar).toBeHidden();
    return;
  }
  // Not while the big title is in view.
  await expect(bar).not.toHaveAttribute("data-shown");
  await page.mouse.wheel(0, 900);
  await expect(bar).toHaveAttribute("data-shown", "");
  await expect(bar).toHaveText("Settings");
  await expect(bar).toBeInViewport();
  // It's a visual echo: screen readers still find only the real heading.
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  await page.mouse.wheel(0, -2000);
  await expect(bar).not.toHaveAttribute("data-shown");
});

test("the title bar follows to the next page", async ({ page, isMobile }) => {
  test.skip(!isMobile, "phones only");
  const user = newUser("Joy");
  await signIn(page, user);
  await page.goto("/you/settings");
  // Wait for the page to fill in, or there's nothing to scroll yet.
  await expect(page.getByRole("heading", { name: "Your data" })).toBeVisible();
  await page.mouse.wheel(0, 900);
  await expect(page.locator("[data-compact-title]")).toHaveAttribute("data-shown", "");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "You" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(user.name);
  await expect(page.getByRole("region", { name: "Crew points" })).toBeVisible();
  // A new page starts at the top, so the bar is gone until you scroll again.
  await expect(page.locator("[data-compact-title]")).not.toHaveAttribute("data-shown");
  await page.mouse.wheel(0, 900);
  await expect(page.locator("[data-compact-title]")).toHaveText(user.name);
});
