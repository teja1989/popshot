import { expect, test, type Page } from "@playwright/test";

import { newUser, signIn } from "./auth";

// Bottom sheets on phones close when dragged down by their grip; a short drag springs back.
// On wider screens they're centred cards with no grip.

async function openStartAGroup(page: Page) {
  await page.goto("/");
  await page.getByRole("button", { name: "Start a group" }).first().click();
  const sheet = page.getByRole("dialog", { name: "Start a group" });
  await expect(sheet).toBeVisible();
  return sheet;
}

async function dragGrip(page: Page, by: number, whileHeld?: () => Promise<void>) {
  const grip = page.locator("[data-sheet-grip]");
  const box = await grip.boundingBox();
  if (!box) {
    throw new Error("No grip");
  }
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  // In small steps, slowly, so it reads as a drag rather than a flick.
  for (let step = 1; step <= 10; step++) {
    await page.mouse.move(x, y + (by * step) / 10);
    await page.waitForTimeout(30);
  }
  await page.waitForTimeout(150);
  await whileHeld?.();
  await page.mouse.up();
}

test("a bottom sheet closes when dragged down, and springs back from a short drag", async ({ page, isMobile }) => {
  await signIn(page, newUser("Gus"));
  const sheet = await openStartAGroup(page);
  if (!isMobile) {
    await expect(page.locator("[data-sheet-grip]")).toHaveCount(0);
    return;
  }

  // Let it finish rising into place before measuring where that is.
  await expect.poll(() => sheet.evaluate((el) => getComputedStyle(el).transform)).toBe("none");
  const before = (await sheet.boundingBox())?.y ?? 0;
  // It follows the pointer while held...
  await dragGrip(page, 40, async () => {
    expect(((await sheet.boundingBox())?.y ?? 0) - before).toBeGreaterThan(30);
  });
  // ...and, let go that close to the top, stays open.
  await expect(sheet).toBeVisible();
  // Back where it was.
  await expect.poll(async () => Math.abs(((await sheet.boundingBox())?.y ?? 0) - before)).toBeLessThan(2);

  // Dragged up, it stays put at the top.
  await dragGrip(page, -60, async () => {
    expect(Math.abs(((await sheet.boundingBox())?.y ?? 0) - before)).toBeLessThan(2);
  });

  await dragGrip(page, 300);
  await expect(sheet).toHaveCount(0);
  // Focus goes back to the button that opened it.
  await expect(page.getByRole("button", { name: "Start a group" }).first()).toBeFocused();
});

test("Escape and the Close button still close a sheet", async ({ page }) => {
  await signIn(page, newUser("Hal"));
  await openStartAGroup(page);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  const sheet = await openStartAGroup(page);
  await sheet.getByRole("button", { name: "Close" }).click();
  // It slides away rather than vanishing, then is gone, with focus back on its button.
  await expect(page.getByRole("dialog")).toHaveCount(0, { timeout: 1000 });
  await expect(page.getByRole("button", { name: "Start a group" }).first()).toBeFocused();
});
