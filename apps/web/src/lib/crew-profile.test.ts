import { describe, expect, it } from "vitest";

import { usualLine } from "./crew-profile";

describe("crew profile", () => {
  it("says when the crew usually plays", () => {
    expect(usualLine({ usual_days: [], usual_times: [] })).toBeNull();
    expect(usualLine({ usual_days: ["sat", "tue", "thu"], usual_times: ["evening", "morning"] })).toBe(
      "Usually Tue, Thu and Sat · mornings and evenings",
    );
    expect(usualLine({ usual_days: ["sun"], usual_times: [] })).toBe("Usually Sun");
    expect(usualLine({ usual_days: [], usual_times: ["midday"] })).toBe("Usually middays");
    expect(usualLine({ usual_days: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"], usual_times: ["evening"] })).toBe(
      "Usually every day · evenings",
    );
  });
});

describe("links", () => {
  it("spots links and addresses, not ordinary dots", async () => {
    const { hasLink } = await import("./crew-profile");
    for (const text of ["https://x.y", "www.club.org", "a@b.co", "join foo.com now"]) {
      expect(hasLink(text), text).toBe(true);
    }
    for (const text of ["Dr. Lee's group", "St. James Rec", "e.g. drills first"]) {
      expect(hasLink(text), text).toBe(false);
    }
  });
});
