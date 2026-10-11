import { describe, expect, it } from "vitest";

import { hasHighlights, record, streakText, upsetLine, type UpsetOut } from "./stats";

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
