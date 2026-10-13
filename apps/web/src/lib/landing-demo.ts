// The made-up game the landing page plays out: who won each rally, in order. It ends 11–9,
// and nobody reaches 11 with a two-point lead any sooner (a test checks).
export const DEMO_RALLIES = "ABAABBABAABBABBAABAA" as const;

export interface DemoScore {
  a: number;
  b: number;
}

/** The score after the first `played` rallies. */
export function demoScore(played: number): DemoScore {
  let a = 0;
  let b = 0;
  for (const winner of DEMO_RALLIES.slice(0, Math.max(0, played))) {
    if (winner === "A") {
      a += 1;
    } else {
      b += 1;
    }
  }
  return { a, b };
}

/** A real final score: someone has 11 or more and leads by 2. */
export function isGameOver({ a, b }: DemoScore): boolean {
  return Math.max(a, b) >= 11 && Math.abs(a - b) >= 2;
}
