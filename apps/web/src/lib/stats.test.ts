import { describe, expect, it } from "vitest";

import {
  busiestDay,
  hasHighlights,
  linePoints,
  record,
  statsPath,
  streakText,
  upsetLine,
  weeklyCounts,
  weekStart,
  type UpsetOut,
} from "./stats";

const ref = (name: string) => ({ player_id: name, display_name: name, is_guest: false });

describe("stats formatting", () => {
  it("records put wins first", () => {
    expect(record(5, 2)).toBe("5–2");
  });

  it.each([
    [null, null],
    [{ result: "W" as const, length: 1 }, "Won the last one"],
    [{ result: "W" as const, length: 4 }, "Won 4 in a row"],
    [{ result: "L" as const, length: 2 }, "Lost 2 in a row"],
  ])("streakText(%j)", (streak, expected) => {
    expect(streakText(streak)).toBe(expected);
  });

  it("upset line names both teams", () => {
    const upset: UpsetOut = {
      match_id: "m",
      played_at: "2026-10-01T18:00:00Z",
      winners: [ref("Casey"), ref("Sam")],
      losers: [ref("Riley"), ref("Alex")],
      gap: 0.4,
    };
    expect(upsetLine(upset)).toBe("Casey & Sam beat Riley & Alex");
  });

  it("knows when there's nothing to highlight", () => {
    expect(hasHighlights({ longest_win_streak: null, most_games: null, biggest_upset: null, window_days: 30 })).toBe(false);
    expect(
      hasHighlights({ longest_win_streak: { player: ref("Jo"), length: 2 }, most_games: null, biggest_upset: null, window_days: 30 }),
    ).toBe(true);
  });
});

describe("dashboard helpers", () => {
  // Wednesday 15 Oct 2025, local time.
  const now = new Date(2025, 9, 15, 12);
  const at = (y: number, m: number, d: number, h = 18) => ({ played_at: new Date(y, m, d, h).toISOString() });

  it("statsPath", () => {
    expect(statsPath("g", 30)).toBe("/v1/groups/g/stats/me?days=30");
    expect(statsPath("g", null)).toBe("/v1/groups/g/stats/me");
  });

  it("weeks start on Monday", () => {
    expect(weekStart(now)).toEqual(new Date(2025, 9, 13));
    expect(weekStart(new Date(2025, 9, 19, 23))).toEqual(new Date(2025, 9, 13)); // Sunday
    expect(weekStart(new Date(2025, 9, 20, 0, 30))).toEqual(new Date(2025, 9, 20)); // Monday
  });

  it("counts matches per week across the window", () => {
    const weeks = weeklyCounts([at(2025, 8, 20), at(2025, 9, 6), at(2025, 9, 7), at(2025, 9, 14)], 30, now);
    // 30 days back from 15 Oct is 15 Sep, in the week of Mon 15 Sep: five weeks.
    expect(weeks.map((w) => w.start.getDate())).toEqual([15, 22, 29, 6, 13]);
    expect(weeks.map((w) => w.count)).toEqual([1, 0, 0, 2, 1]);
  });

  it("all time starts at your first game, capped", () => {
    const weeks = weeklyCounts([at(2025, 9, 1)], null, now);
    expect(weeks.map((w) => w.count)).toEqual([1, 0, 0]);
    expect(weeklyCounts([at(2020, 0, 1)], null, now, 26)).toHaveLength(26);
    expect(weeklyCounts([], null, now)).toEqual([{ start: new Date(2025, 9, 13), count: 0 }]);
  });

  it("busiest day", () => {
    expect(busiestDay([])).toBeNull();
    expect(busiestDay([at(2025, 9, 14), at(2025, 9, 7), at(2025, 9, 9)])).toBe("Tuesday");
    // One Sunday, one Monday: Monday wins the tie.
    expect(busiestDay([at(2025, 9, 12), at(2025, 9, 13)])).toBe("Monday");
  });

  it("line points fill the box", () => {
    expect(linePoints([], 100, 50)).toEqual([]);
    expect(linePoints([3], 100, 50)).toEqual([{ x: 50, y: 25 }]);
    const pts = linePoints([3, 4, 3.5], 100, 50, 0);
    expect(pts).toEqual([
      { x: 0, y: 50 },
      { x: 50, y: 0 },
      { x: 100, y: 25 },
    ]);
  });
});
