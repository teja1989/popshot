import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  change,
  CREW_POINTS,
  DEFAULT_START,
  edgeText,
  everyone,
  LEVELS,
  levelLabel,
  points,
  trendSummary,
  winRate,
  type MyRating,
} from "./board";

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

function crew(name: string, trend: MyRating["trend"], edge: number | null): MyRating {
  return {
    group_id: name,
    group_name: name,
    rating: 3.4,
    matches: 20,
    rank: 1,
    ranked_of: 4,
    to_go: 0,
    form: [],
    week_games: 2,
    month_games: trend === null ? 2 : 8,
    month_change: 0.1,
    month_edge: edge,
    trend,
  };
}

describe("comparing crews", () => {
  it("describes the share of points against expected", () => {
    expect(edgeText(0.041)).toBe("4% more of the points than expected");
    expect(edgeText(-0.032)).toBe("3% fewer of the points than expected");
    expect(edgeText(0.004)).toBe("points won as expected");
  });

  it("needs two crews with a trend to compare", () => {
    expect(trendSummary([])).toBeNull();
    expect(trendSummary([crew("Thursday", "climbing", 0.05)])).toBeNull();
    expect(trendSummary([crew("Thursday", "climbing", 0.05), crew("Sunday", null, -0.2)])).toBeNull();
  });

  it("names where it's going well and where to focus", () => {
    const ratings = [
      crew("Sunday", "slipping", -0.04),
      crew("Thursday", "climbing", 0.05),
      crew("Office", "steady", 0.0),
    ];
    expect(trendSummary(ratings)).toBe("Going well in Thursday; Sunday is where to focus.");
    expect(trendSummary([crew("Thursday", "climbing", 0.05), crew("Office", "steady", 0)])).toBe(
      "Going well in Thursday.",
    );
    expect(trendSummary([crew("Sunday", "slipping", -0.04), crew("Office", "steady", 0)])).toBe(
      "Sunday is where to focus.",
    );
    expect(trendSummary([crew("Office", "steady", 0.01), crew("Park", "steady", -0.01)])).toBe(
      "Steady across your crews.",
    );
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
    example: {
      team: number;
      opponents: number;
      score: number[];
      expected_share: number;
      change_settled: number;
      change_new: number;
    };
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

describe("everyone", () => {
  const row = (display_name: string) => ({
    player_id: display_name,
    display_name,
    avatar_url: null,
    is_guest: false,
    is_me: false,
    rating: 3,
    reliability: 0,
    matches: 1,
    wins: 0,
    form: [],
    week_change: null,
    rank: null,
    to_go: 0,
  });

  it("lists the whole crew A to Z, never by points", () => {
    const board = {
      ranked: [row("Riley"), row("alex")],
      getting_started: [row("Casey")],
      resting: [row("Bo")],
      ranked_after: 10,
      resting_after_days: 60,
    };
    expect(everyone(board).map((r) => r.display_name)).toEqual(["alex", "Bo", "Casey", "Riley"]);
  });
});
