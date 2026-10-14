// The line under the greeting on Home: a different bit of pickleball fun on each visit.
// Plain words, no rankings, nobody's left out.
const ONE_LAST_GAME = "One last game? It's never the last one.";

export const COURT_LINES: readonly string[] = [
  ONE_LAST_GAME,
  "Play, laugh, stay active. Popshot keeps the score.",
  "Dink responsibly.",
  "The kitchen is closed. Unless it bounced.",
  "Soft hands, big smiles.",
  "Every rally teaches you something.",
  "Zero, zero, start. Let's play.",
  "Warm-up dinks count as cardio.",
  "Bring water, bring friends, bring a spare ball.",
  "Third shot drop: easy to say, fun to practise.",
  "Your paddle misses you.",
  "Win or learn. Either way, play again.",
  "Who called the score? Everyone, at once.",
  "Keep calm and dink on.",
  "Long rally? That's the good stuff.",
  "Paddle up. The court is calling.",
  "Ready, set, dink.",
  "Kitchen rules: be kind, mind the line.",
  "Good games start with a good warm-up.",
  "Same court, new rally. See you there.",
];

const LAST_KEY = "popshot.court-line";

// A line other than `previous` (when there's a choice). `random` returns [0, 1).
export function pickLine(previous: string | null, random: () => number = Math.random): string {
  const choices = COURT_LINES.filter((line) => line !== previous);
  return choices[Math.min(choices.length - 1, Math.floor(random() * choices.length))] ?? ONE_LAST_GAME;
}

// Picks today's line in the browser and remembers it, so the next visit shows another.
export function nextCourtLine(): string {
  let previous: string | null = null;
  try {
    previous = window.localStorage.getItem(LAST_KEY);
  } catch {
    // No storage (private window, blocked): just random.
  }
  const line = pickLine(previous);
  try {
    window.localStorage.setItem(LAST_KEY, line);
  } catch {
    // Same as above.
  }
  return line;
}
