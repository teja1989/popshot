import { expect, test, type Page } from "@playwright/test";

import { apiAs } from "./api";
import { newUser, signIn } from "./auth";
import { watchProblems } from "./problems";

// The lead's device is in India, so the zone can't be the test machine's by chance.
test.use({ timezoneId: "Asia/Kolkata" });

async function zoneOf(page: Page, crewId: string): Promise<string | null> {
  const crew = (await apiAs(page, "GET", `/v1/groups/${crewId}`)) as { time_zone: string | null };
  return crew.time_zone;
}

test("a new crew takes its lead's time zone, and the lead can change it", async ({ page }) => {
  await signIn(page, newUser("Tara"));
  const problems = await watchProblems(page);
  const name = `Zone ${String(Date.now()).slice(-6)}`;
  await page.goto("/");
  await page.getByRole("button", { name: "Start a group" }).first().click();
  await page.getByLabel("Group name").fill(name);
  await page.getByRole("button", { name: "Create group" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(name);
  const crewId = /\/groups\/([0-9a-f-]{36})/.exec(page.url())?.[1] ?? "";
  expect(await zoneOf(page, crewId)).toBe("Asia/Kolkata");

  await page.goto(`/groups/${crewId}/settings`);
  const section = page.getByRole("region", { name: "Group", exact: true });
  const zone = section.getByLabel("Time zone");
  await expect(zone).toHaveValue("Asia/Kolkata");
  await expect(section).toContainText("Your crew's days follow this clock.");
  const save = section.getByRole("button", { name: "Save time zone" });
  await expect(save).toBeDisabled();
  await zone.selectOption("Europe/London");
  await save.click();
  await expect(section.getByText("Saved.")).toBeVisible();
  await page.reload();
  await expect(section.getByLabel("Time zone")).toHaveValue("Europe/London");
  expect(await zoneOf(page, crewId)).toBe("Europe/London");
  expect(problems).toEqual([]);
});

test("an older crew gets its time zone once its lead opens it", async ({ page }) => {
  await signIn(page, newUser("Ira"));
  await page.goto("/");
  // As crews made before zones were kept: none sent.
  const crew = (await apiAs(page, "POST", "/v1/groups", { name: `Old ${String(Date.now())}` })) as {
    id: string;
    time_zone: string | null;
  };
  expect(crew.time_zone).toBeNull();

  await page.goto(`/groups/${crew.id}`);
  await expect.poll(() => zoneOf(page, crew.id)).toBe("Asia/Kolkata");
});

test.describe("on a device that reports an old zone name", () => {
  test.use({ timezoneId: "Europe/Kiev" });

  test("the crew keeps the zone's current name", async ({ page }) => {
    await signIn(page, newUser("Oksana"));
    await page.goto("/");
    const crew = (await apiAs(page, "POST", "/v1/groups", {
      name: `Kyiv ${String(Date.now())}`,
      time_zone: await page.evaluate(() => Intl.DateTimeFormat().resolvedOptions().timeZone),
    })) as { id: string; time_zone: string | null };
    expect(crew.time_zone).toBe("Europe/Kyiv");
  });
});
