import { describe, expect, it } from "vitest";

import { byDay, daysShown, dayKey, rangeOf, step, titleOf } from "./calendar";

// Local dates: these tests don't depend on the machine's time zone.
const sunday = new Date(2026, 9, 11); // Sun Oct 11 2026
const wednesday = new Date(2026, 9, 14, 18, 30);

describe("calendar", () => {
  it("a week runs Sunday to Saturday", () => {
    expect(daysShown("week", wednesday).map(dayKey)).toEqual([
      "2026-10-11",
      "2026-10-12",
      "2026-10-13",
      "2026-10-14",
      "2026-10-15",
      "2026-10-16",
      "2026-10-17",
    ]);
    expect(daysShown("week", sunday).map(dayKey)[0]).toBe("2026-10-11");
  });

  it("a month is whole weeks around it", () => {
    const october = daysShown("month", wednesday);
    expect(dayKey(october[0] ?? sunday)).toBe("2026-09-27");
    expect(dayKey(october[october.length - 1] ?? sunday)).toBe("2026-10-31");
    expect(october).toHaveLength(35);
    // February 2026 starts on a Sunday and fits four weeks exactly.
    expect(daysShown("month", new Date(2026, 1, 10))).toHaveLength(28);
  });

  it("asks the API for the days shown, end exclusive", () => {
    const { start, end } = rangeOf(daysShown("week", wednesday));
    expect([dayKey(start), dayKey(end)]).toEqual(["2026-10-11", "2026-10-18"]);
  });

  it("steps by a week or a month", () => {
    expect(dayKey(step("week", wednesday, 1))).toBe("2026-10-21");
    expect(dayKey(step("month", new Date(2026, 0, 31), 1))).toBe("2026-02-01");
    expect(dayKey(step("month", new Date(2026, 0, 31), -1))).toBe("2025-12-01");
  });

  it("titles", () => {
    expect(titleOf("week", wednesday, "en-US")).toBe("Oct 11 – 17");
    expect(titleOf("week", new Date(2026, 9, 28), "en-US")).toBe("Oct 25 – 31");
    expect(titleOf("week", new Date(2026, 10, 2), "en-US")).toBe("Nov 1 – 7");
    expect(titleOf("week", new Date(2026, 8, 30), "en-US")).toBe("Sep 27 – Oct 3");
    expect(titleOf("month", wednesday, "en-US")).toBe("October 2026");
  });

  it("groups items by local day", () => {
    const items = [
      { at: new Date(2026, 9, 14, 9).toISOString(), id: 1 },
      { at: new Date(2026, 9, 14, 20).toISOString(), id: 2 },
      { at: new Date(2026, 9, 15, 8).toISOString(), id: 3 },
    ];
    const days = byDay(items, (i) => i.at);
    expect(days.get("2026-10-14")?.map((i) => i.id)).toEqual([1, 2]);
    expect(days.get("2026-10-15")?.map((i) => i.id)).toEqual([3]);
  });
});
