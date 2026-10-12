import { describe, expect, it } from "vitest";

import { describeMatch, namesOn, playedWhen, scoreLine, teamNames, toLocalInput } from "./games";

const players = [
  { player_id: "1", display_name: "Casey", is_guest: false, team: "A" as const },
  { player_id: "2", display_name: "Gary", is_guest: true, team: "A" as const },
  { player_id: "3", display_name: "Sam", is_guest: false, team: "B" as const },
];

describe("names", () => {
  it("joins a team", () => {
    expect(teamNames(["Casey", "Gary"])).toBe("Casey & Gary");
    expect(namesOn({ players }, "A")).toBe("Casey & Gary");
    expect(namesOn({ players }, "B")).toBe("Sam");
  });
});

describe("scoreLine", () => {
  it("reads from the winner's side", () => {
    const games = [
      { team_a: 11, team_b: 7 },
      { team_a: 9, team_b: 11 },
      { team_a: 8, team_b: 11 },
    ];
    expect(scoreLine({ games, winner: "B" })).toBe("7–11, 11–9, 11–8");
    expect(scoreLine({ games: [{ team_a: 11, team_b: 4 }], winner: "A" })).toBe("11–4");
  });
});

describe("playedWhen", () => {
  const now = new Date(2026, 9, 11, 20, 0);
  it.each([
    [new Date(2026, 9, 11, 18, 40), /^Today, /],
    [new Date(2026, 9, 10, 9, 5), /^Yesterday, /],
    [new Date(2026, 9, 4, 10, 0), /^Sun,? 4 Oct, /],
  ])("%s", (when, expected) => {
    expect(playedWhen(when.toISOString(), now, "en-GB")).toMatch(expected);
  });
});

describe("toLocalInput", () => {
  it("formats for datetime-local", () => {
    expect(toLocalInput(new Date(2026, 0, 5, 7, 3))).toBe("2026-01-05T07:03");
  });
});

describe("describeMatch", () => {
  it("puts the rules in one line", () => {
    expect(describeMatch({ format: "doubles", bestOf: 1, pointsTo: 11, winByTwo: true })).toBe(
      "Doubles · 1 game · to 11, win by 2",
    );
    expect(describeMatch({ format: "singles", bestOf: 5, pointsTo: 15, winByTwo: false })).toBe(
      "Singles · best of 5 · to 15, no win by 2",
    );
  });
});
