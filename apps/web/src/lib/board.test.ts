import { describe, expect, it } from "vitest";

import { change, levelLabel, points, winRate } from "./board";

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
