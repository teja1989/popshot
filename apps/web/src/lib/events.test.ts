import { describe, expect, it } from "vitest";

import {
  formatInfo,
  openCourts,
  pointDifference,
  roundShape,
  roundsIn,
  scoreText,
  shapeLine,
  suggestFormat,
  teamLine,
  type EventRound,
} from "./events";

describe("crew events", () => {
  it("says how a round works out", () => {
    expect(roundShape(9, 2)).toEqual({ courts: 2, playing: 8, sittingOut: 1 });
    expect(roundShape(9, 4)).toEqual({ courts: 2, playing: 8, sittingOut: 1 });
    expect(roundShape(4, 1)).toEqual({ courts: 1, playing: 4, sittingOut: 0 });
    expect(shapeLine(9, 2)).toBe("8 play each round on 2 courts, 1 sits out.");
    expect(shapeLine(10, 2)).toBe("8 play each round on 2 courts, 2 sit out.");
    expect(shapeLine(4, 3)).toBe("4 play each round on 1 court, nobody sits out.");
    expect(shapeLine(3, 1)).toBe("Pick at least 4 players.");
  });

  it("estimates rounds from the time you have", () => {
    expect(roundsIn(90)).toBe(6);
    expect(roundsIn(90, 3)).toBe(2);
    expect(roundsIn(5)).toBe(1);
  });

  it("suggests River only with two courts to move between", () => {
    expect(suggestFormat(9, 2, ["shuffle", "river"])?.kind).toBe("river");
    expect(suggestFormat(6, 2, ["shuffle", "river"])?.kind).toBe("shuffle");
    expect(suggestFormat(12, 3, ["shuffle"])?.kind).toBe("shuffle");
    expect(suggestFormat(8, 2, [])).toBeNull();
    expect(suggestFormat(6, 1, ["river"])?.kind).toBe("river");
  });

  it("names formats the playful way, with the standard name too", () => {
    expect(formatInfo("shuffle").name).toBe("Dink Shuffle");
    expect(formatInfo("river").standard).toBe("Up and down the river");
  });

  it("finds the courts still waiting for a score", () => {
    const round: EventRound = {
      number: 1,
      sitting_out: [],
      courts: [
        { court: 1, team_a: [], team_b: [], match_id: "m", games: [], winner: "A", skipped: false },
        { court: 2, team_a: [], team_b: [], match_id: null, games: [], winner: null, skipped: true },
        { court: 3, team_a: [], team_b: [], match_id: null, games: [], winner: null, skipped: false },
      ],
    };
    expect(openCourts(round).map((c) => c.court)).toEqual([3]);
  });

  it("writes scores, teams and point differences", () => {
    expect(
      scoreText([
        { team_a: 11, team_b: 9 },
        { team_a: 8, team_b: 11 },
      ]),
    ).toBe("11–9, 8–11");
    const names = new Map([
      ["a", "Ana"],
      ["b", "Bo"],
    ]);
    expect(teamLine(["a", "b"], names)).toBe("Ana & Bo");
    expect(teamLine(["a", "x"], names)).toBe("Ana & Someone");
    expect(pointDifference({ points_for: 30, points_against: 18 })).toBe("+12");
    expect(pointDifference({ points_for: 18, points_against: 21 })).toBe("−3");
    expect(pointDifference({ points_for: 5, points_against: 5 })).toBe("0");
  });
});
