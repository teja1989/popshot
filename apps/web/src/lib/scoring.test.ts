import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import {
  gamesToShow,
  MAX_POINTS,
  validateGame,
  validateMatch,
  type BestOf,
  type GameRules,
  type PointsTo,
} from "./scoring";

interface Shared {
  games: { points_to: PointsTo; win_by_two: boolean; a: number; b: number; ok: boolean }[];
  matches: {
    points_to: PointsTo;
    win_by_two: boolean;
    best_of: BestOf;
    games: [number, number][];
    winner: "A" | "B" | null;
  }[];
}

// The API's tests read the same file (services/api/tests/test_scoring.py).
const shared = JSON.parse(
  readFileSync(join(__dirname, "..", "..", "..", "..", "shared", "score-cases.json"), "utf8"),
) as Shared;

describe("shared cases", () => {
  it.each(shared.games)("$a-$b to $points_to (win by 2: $win_by_two)", (c) => {
    expect(validateGame({ pointsTo: c.points_to, winByTwo: c.win_by_two }, c.a, c.b).ok).toBe(c.ok);
  });

  it.each(shared.matches)("best of $best_of: $games", (c) => {
    const result = validateMatch({ pointsTo: c.points_to, winByTwo: c.win_by_two }, c.best_of, c.games);
    expect(result.ok ? result.value : null).toBe(c.winner);
  });
});

// An independent oracle, as in the API's property tests: a score is final if the game is
// over at it, and it could be reached one rally at a time without the game ending earlier.
function over(rules: GameRules, a: number, b: number): boolean {
  const lead = Math.abs(a - b);
  return Math.max(a, b) >= rules.pointsTo && lead >= (rules.winByTwo ? 2 : 1);
}

/** Every score up to max-max that a game can reach, as "a-b". */
function reachableScores(rules: GameRules, max: number): Set<string> {
  const reachable = new Set<string>(["0-0"]);
  for (let a = 0; a <= max; a++) {
    for (let b = 0; b <= max; b++) {
      const fromA = a > 0 && reachable.has(`${String(a - 1)}-${String(b)}`) && !over(rules, a - 1, b);
      const fromB = b > 0 && reachable.has(`${String(a)}-${String(b - 1)}`) && !over(rules, a, b - 1);
      if (fromA || fromB) {
        reachable.add(`${String(a)}-${String(b)}`);
      }
    }
  }
  return reachable;
}

describe("validateGame against the rally oracle", () => {
  const all: GameRules[] = [11, 15, 21].flatMap((pointsTo) =>
    [true, false].map((winByTwo) => ({ pointsTo: pointsTo as PointsTo, winByTwo })),
  );
  it.each(all)("every score up to 40 for $pointsTo, win by 2 $winByTwo", (rules) => {
    const reachable = reachableScores(rules, 40);
    for (let a = 0; a <= 40; a++) {
      for (let b = 0; b <= 40; b++) {
        const final = over(rules, a, b) && reachable.has(`${String(a)}-${String(b)}`);
        const result = validateGame(rules, a, b);
        expect(result.ok, `${String(a)}-${String(b)}`).toBe(final);
        if (result.ok) {
          expect(result.value).toBe(a > b ? "A" : "B");
        }
      }
    }
  });

  it.each([-1, MAX_POINTS + 1, 11.5, Number.NaN])("rejects %s", (bad) => {
    expect(validateGame({ pointsTo: 11, winByTwo: true }, bad, 0).ok).toBe(false);
  });

  it("explains the problem", () => {
    const result = validateGame({ pointsTo: 11, winByTwo: true }, 11, 10);
    expect(result).toEqual({ ok: false, problem: "Past game point, the winner finishes exactly two points ahead." });
  });
});

describe("validateMatch", () => {
  it("names the game with the problem in a best of 3", () => {
    const result = validateMatch({ pointsTo: 11, winByTwo: true }, 3, [
      [11, 4],
      [11, 10],
    ]);
    expect(result).toEqual({
      ok: false,
      problem: "Game 2: Past game point, the winner finishes exactly two points ahead.",
    });
  });
});

describe("gamesToShow", () => {
  const rules: GameRules = { pointsTo: 11, winByTwo: true };
  it.each([
    [1, [], 1],
    [3, [], 2],
    [3, [[11, 4]], 2],
    [
      3,
      [
        [11, 4],
        [11, 6],
      ],
      2,
    ],
    [
      3,
      [
        [11, 4],
        [6, 11],
      ],
      3,
    ],
    [
      3,
      [
        [11, 4],
        [6, 10],
      ],
      2,
    ],
    [5, [], 3],
    [
      5,
      [
        [11, 4],
        [11, 6],
      ],
      3,
    ],
    [
      5,
      [
        [11, 4],
        [11, 6],
        [11, 2],
      ],
      3,
    ],
    [
      5,
      [
        [11, 4],
        [6, 11],
        [11, 2],
      ],
      4,
    ],
    [
      5,
      [
        [11, 4],
        [6, 11],
        [11, 2],
        [3, 11],
      ],
      5,
    ],
    [
      5,
      [
        [11, 4],
        [6, 11],
        [11, 2],
        [11, 3],
      ],
      4,
    ],
    [
      5,
      [
        [11, 4],
        [6, 11],
        [11, 2],
        [3, 10],
      ],
      4,
    ],
  ] as const)("best of %i with %j -> %i rows", (bestOf, games, rows) => {
    expect(gamesToShow(bestOf, rules, games)).toBe(rows);
  });
});
