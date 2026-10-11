import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { change, CREW_POINTS, DEFAULT_START, LEVELS, levelLabel, points, winRate } from "./board";

describe("board formatting", () => {
  it("shows crew points with two decimals", () => {
    expect(points(3.4712)).toBe("3.47");
    expect(points(6)).toBe("6.00");
  });

  it.each([
    [0.123, { text: "▲ 0.12", up: true }],
    [-0.05, { text: "▼ 0.05", up: false }],
    [0.001, null],
    [null, null],
  ])("change(%s)", (value, expected) => {
    expect(change(value)).toEqual(expected);
  });

  it("win rate", () => {
    expect(winRate({ wins: 7, matches: 10 })).toBe("70%");
    expect(winRate({ wins: 0, matches: 0 })).toBe("–");
  });

  it("level labels", () => {
    expect(levelLabel("advanced")).toBe("Advanced");
    expect(levelLabel(null)).toBeNull();
  });
});

describe("the crew points explanation", () => {
  const shared = JSON.parse(
    readFileSync(join(__dirname, "..", "..", "..", "..", "shared", "crew-points.json"), "utf8"),
  ) as {
    min: number;
    max: number;
    start: number;
    steady_after: number;
    ranked_after: number;
    resting_after_days: number;
    level_start: Record<string, number>;
    example: { team: number; opponents: number; score: number[]; expected_share: number; change_settled: number; change_new: number };
  };

  it("matches the rules the API uses", () => {
    expect([CREW_POINTS.min, CREW_POINTS.max, DEFAULT_START]).toEqual([shared.min, shared.max, shared.start]);
    expect(CREW_POINTS.steadyAfter).toBe(shared.steady_after);
    expect(CREW_POINTS.rankedAfter).toBe(shared.ranked_after);
    expect(CREW_POINTS.restingAfterDays).toBe(shared.resting_after_days);
    expect(Object.fromEntries(LEVELS.map((l) => [l.value, l.start]))).toEqual(shared.level_start);
    const ex = CREW_POINTS.example;
    expect([ex.team, ex.opponents, [...ex.score], ex.expectedShare, ex.changeSettled, ex.changeNew]).toEqual([
      shared.example.team,
      shared.example.opponents,
      shared.example.score,
      shared.example.expected_share,
      shared.example.change_settled,
      shared.example.change_new,
    ]);
  });
});
