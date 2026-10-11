import { describe, expect, it } from "vitest";

import { describeRules, timeLeft } from "./groups";

describe("groups", () => {
  const now = new Date("2026-10-11T12:00:00Z");

  it.each([
    ["2026-11-10T12:00:00Z", "30 days"],
    ["2026-11-10T11:59:00Z", "30 days"],
    ["2026-10-13T11:00:00Z", "2 days"],
    ["2026-10-12T12:00:00Z", "1 day"],
    ["2026-10-12T11:59:00Z", "less than a day"],
    ["2026-10-10T12:00:00Z", "less than a day"],
  ])("timeLeft(%s)", (until, expected) => {
    expect(timeLeft(until, now)).toBe(expected);
  });

  it("describes rules", () => {
    expect(describeRules({ default_format: "singles", default_points_to: 15, default_win_by_two: false })).toBe(
      "Singles · games to 15",
    );
    expect(describeRules({ default_format: "doubles", default_points_to: 11, default_win_by_two: true })).toBe(
      "Doubles · games to 11, win by 2",
    );
  });
});
