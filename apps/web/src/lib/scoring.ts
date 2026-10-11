// Score rules for a game and a best-of-N match. A copy of the API's scoring.py, so the log
// screen can explain a bad score as you type. The API checks again and has the final say.
// Both are tested against shared/score-cases.json, so they can't drift apart.

export type Team = "A" | "B";
export type PointsTo = 11 | 15 | 21;
export type BestOf = 1 | 3;

export interface GameRules {
  pointsTo: PointsTo;
  winByTwo: boolean;
}

export const MAX_POINTS = 99;

export type Checked<T> = { ok: true; value: T } | { ok: false; problem: string };

function fail<T>(problem: string): Checked<T> {
  return { ok: false, problem };
}

export function validateGame(rules: GameRules, a: number, b: number): Checked<Team> {
  for (const points of [a, b]) {
    if (!Number.isInteger(points)) {
      return fail("Scores must be whole numbers.");
    }
    if (points < 0 || points > MAX_POINTS) {
      return fail(`Scores must be between 0 and ${String(MAX_POINTS)}.`);
    }
  }
  if (a === b) {
    return fail("A game can't end in a tie.");
  }
  const winner = Math.max(a, b);
  const loser = Math.min(a, b);
  const target = rules.pointsTo;

  if (!rules.winByTwo) {
    if (winner !== target) {
      return fail(`Without win-by-2, the winner finishes on exactly ${String(target)}.`);
    }
  } else if (loser <= target - 2) {
    if (winner !== target) {
      return fail(`The winner finishes on ${String(target)} when the other side has ${String(loser)}.`);
    }
  } else if (winner !== loser + 2) {
    return fail("Past game point, the winner finishes exactly two points ahead.");
  }
  return { ok: true, value: a > b ? "A" : "B" };
}

export function validateMatch(rules: GameRules, bestOf: BestOf, games: readonly (readonly [number, number])[]): Checked<Team> {
  if (games.length === 0) {
    return fail("Enter at least one game.");
  }
  const needed = Math.floor(bestOf / 2) + 1;
  const wins = { A: 0, B: 0 };
  for (const [index, [a, b]] of games.entries()) {
    if (Math.max(wins.A, wins.B) === needed) {
      return fail(`The match was already decided before game ${String(index + 1)}.`);
    }
    const game = validateGame(rules, a, b);
    if (!game.ok) {
      return games.length > 1 ? fail(`Game ${String(index + 1)}: ${game.problem}`) : game;
    }
    wins[game.value] += 1;
  }
  if (wins.A === needed) {
    return { ok: true, value: "A" };
  }
  if (wins.B === needed) {
    return { ok: true, value: "B" };
  }
  return fail("The match isn't finished yet.");
}

/** How many score rows to show for a best-of-3 so far: 2, or 3 once it's one game each. */
export function gamesToShow(bestOf: BestOf, rules: GameRules, games: readonly (readonly [number, number])[]): number {
  if (bestOf === 1) {
    return 1;
  }
  const [first, second] = games;
  if (!first || !second) {
    return 2;
  }
  const one = validateGame(rules, first[0], first[1]);
  const two = validateGame(rules, second[0], second[1]);
  return one.ok && two.ok && one.value !== two.value ? 3 : 2;
}
