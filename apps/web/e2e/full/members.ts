import type { Page } from "@playwright/test";

/** Open the members page of the group `page` is on, unless it's already there. */
export async function toMembers(page: Page): Promise<void> {
  const url = new URL(page.url());
  if (!url.pathname.endsWith("/members")) {
    const group = /^\/groups\/[0-9a-f-]{36}/.exec(url.pathname)?.[0];
    if (!group) {
      throw new Error(`not on a group page: ${url.pathname}`);
    }
    await page.goto(`${group}/members`);
  }
}
