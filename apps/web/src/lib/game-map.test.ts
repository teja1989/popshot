import { describe, expect, it } from "vitest";

import { BANNED } from "./copy-rules";
import {
  BOXES,
  describePoint,
  formPosition,
  mapSummary,
  plotted,
  rhythmPosition,
  weekLabel,
  type GameMap,
  type MapPoint,
} from "./game-map";

function map(points: MapPoint[]): GameMap {
  return { goal: 2, goal_set: false, min_games: 5, window_days: 28, points, crews: [], partners: [] };
}

const now: MapPoint = { ending: "2026-10-17T18:00:00Z", games: 10, per_week: 2.5, form: 0.04, box: "in_the_groove" };
const thin: MapPoint = { ending: "2026-10-10T18:00:00Z", games: 3, per_week: 0.75, form: null, box: null };

describe("the chart's scales", () => {
  it("puts your goal in the middle, and caps at twice it", () => {
    expect(rhythmPosition(0, 2)).toBe(0);
    expect(rhythmPosition(2, 2)).toBe(0.5);
    expect(rhythmPosition(4, 2)).toBe(1);
    expect(rhythmPosition(9, 2)).toBe(1);
  });

  it("puts as-expected in the middle and keeps big swings on the edge", () => {
    expect(formPosition(0)).toBe(0.5);
    expect(formPosition(0.15)).toBe(1);
    expect(formPosition(-0.15)).toBe(0);
    expect(formPosition(0.4)).toBe(1);
    expect(formPosition(-0.4)).toBe(0);
  });
});

describe("words", () => {
  it("describes a point and the whole map", () => {
    expect(describePoint(now)).toBe("2.5 games a week, 4% more of the points than expected");
    expect(describePoint(thin)).toBe("0.8 games a week; not enough games yet to read results");
    expect(mapSummary(map([thin, now]))).toBe("In the groove: 2.5 games a week, 4% more of the points than expected.");
    expect(mapSummary(map([thin]))).toBe("A few more games and your map appears. It needs 5 games in 28 days.");
    expect(weekLabel("2026-10-17T18:00:00Z")).toBe("Week to 17 Oct");
  });

  it("only plots weeks with enough games", () => {
    expect(plotted(map([thin, now]))).toEqual([now]);
  });

  it("never shames or ranks", () => {
    for (const box of Object.values(BOXES)) {
      for (const words of [box.title, box.means, box.next.label]) {
        expect(words).not.toMatch(BANNED);
        expect(words).not.toMatch(/\bAI\b/);
      }
    }
  });
});
