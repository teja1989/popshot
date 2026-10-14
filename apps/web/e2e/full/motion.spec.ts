import { expect, test } from "@playwright/test";

import { newUser, signIn } from "./auth";

// On phones, a slim bar with the page's title slides in once its big title scrolls away.

test("the compact title bar follows the page title on phones", async ({ page, isMobile }) => {
  const user = newUser("Ivy");
  await signIn(page, user);
  await page.goto("/you");
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(user.name);
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
  await expect(bar).toHaveText(user.name);
  await expect(bar).toBeInViewport();
  // It's a visual echo: screen readers still find only the real heading.
  await expect(page.getByRole("heading", { level: 1 })).toHaveCount(1);
  await page.mouse.wheel(0, -2000);
  await expect(bar).not.toHaveAttribute("data-shown");
});

test("the title bar follows to the next page", async ({ page, isMobile }) => {
  test.skip(!isMobile, "phones only");
  await signIn(page, newUser("Joy"));
  await page.goto("/you");
  // Wait for the page to fill in, or there's nothing to scroll yet.
  await expect(page.getByRole("heading", { name: "Your data" })).toBeVisible();
  await page.mouse.wheel(0, 900);
  await expect(page.locator("[data-compact-title]")).toHaveAttribute("data-shown", "");
  await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: "More" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("More");
  await expect(page.getByRole("link", { name: /Sign out|Terms/ }).first()).toBeAttached();
  // A new page starts at the top, so the bar is gone until you scroll again.
  await expect(page.locator("[data-compact-title]")).not.toHaveAttribute("data-shown");
  await page.mouse.wheel(0, 900);
  await expect(page.locator("[data-compact-title]")).toHaveText("More");
});
