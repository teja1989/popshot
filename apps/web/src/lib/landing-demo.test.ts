import { describe, expect, it } from "vitest";

import { DEMO_RALLIES, demoScore, isGameOver } from "./landing-demo";

describe("the landing page's demo game", () => {
  it("ends 11–9", () => {
    expect(demoScore(DEMO_RALLIES.length)).toEqual({ a: 11, b: 9 });
    expect(isGameOver(demoScore(DEMO_RALLIES.length))).toBe(true);
  });

  it("isn't over any sooner", () => {
    for (let played = 0; played < DEMO_RALLIES.length; played += 1) {
      expect(isGameOver(demoScore(played))).toBe(false);
    }
  });

  it("starts at 0–0", () => {
    expect(demoScore(0)).toEqual({ a: 0, b: 0 });
  });
});
