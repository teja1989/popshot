// The landing page's big headline: short lines about pickleball and staying well, shown one
// after another on a scoreboard flip. The `accent` part is in ball colour. Plain, kind words,
// no rankings, no health promises: these are invitations, not claims.

export interface Headline {
  lead: string;
  accent: string;
}

// Always shown first, and the one screen readers, search engines and "reduce motion" get.
export const FIRST: Headline = { lead: "One last", accent: "game." };

export const HEADLINES: readonly Headline[] = [
  FIRST,
  { lead: "Dink more,", accent: "worry less." },
  { lead: "Move more,", accent: "sit less." },
  { lead: "Good rallies,", accent: "good friends." },
  { lead: "Your heart likes", accent: "long rallies." },
  { lead: "Laugh. Sweat.", accent: "Repeat." },
  { lead: "Soft hands,", accent: "big smiles." },
  { lead: "Stay out of", accent: "the kitchen." },
  { lead: "Warm up.", accent: "Then dink." },
  { lead: "Fresh air,", accent: "fast hands." },
  { lead: "Sleep well,", accent: "play better." },
  { lead: "Drink water.", accent: "Then rally." },
  { lead: "Every rally", accent: "counts." },
  { lead: "Play today,", accent: "glow tomorrow." },
];

export function headlineText(headline: Headline): string {
  return `${headline.lead} ${headline.accent}`;
}

/**
 * The order to show them in: the first one, then the rest shuffled, so no two visits look
 * the same. `random` returns [0, 1).
 */
export function headlineOrder(random: () => number = Math.random): Headline[] {
  const rest = HEADLINES.slice(1);
  for (let i = rest.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    const swap = rest[i];
    const other = rest[j];
    if (swap && other) {
      rest[i] = other;
      rest[j] = swap;
    }
  }
  return [FIRST, ...rest];
}

// How long each line stays before the next one flips in.
export const HOLD_MS = 4000;
