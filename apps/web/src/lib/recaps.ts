// Recaps: a crew's outings and what's worth celebrating in each. Shapes match the API's
// routes/recaps.py.

import type { PlayerRef } from "./stats";

export type AwardKind = "always_there" | "great_partner" | "welcome_wagon" | "personal_best" | "close_call";

export interface Award {
  kind: AwardKind;
  players: PlayerRef[];
  // Weeks in a row, partners won with, first-timers welcomed, games played, or close games.
  value: number;
}

export interface RecapSummary {
  key: string;
  start: string;
  end: string;
  games: number;
  players: number;
  venue: string | null;
  headline: string;
}

export interface Recap extends RecapSummary {
  lines: string[];
  // Popshot's own commentator, or Gemini (labelled as AI).
  written_by: "popshot" | "ai";
  newcomers: PlayerRef[];
  awards: Award[];
  played: { player: PlayerRef; games: number }[];
  match_ids: string[];
}

const plural = (n: number, one: string, many: string) => (n === 1 ? one : many);

/** An award's name and what it was for. */
export function describeAward(award: Pick<Award, "kind" | "value">): { title: string; why: string } {
  const n = award.value;
  switch (award.kind) {
    case "always_there":
      return { title: "Always There", why: `${String(n)} weeks in a row` };
    case "great_partner":
      return { title: "Great Partner", why: `Won with ${String(n)} different partners` };
    case "welcome_wagon":
      return {
        title: "Welcome Wagon",
        why: plural(n, "Partnered a first-timer", `Partnered ${String(n)} first-timers`),
      };
    case "personal_best":
      return { title: "Personal Best", why: `${String(n)} games in one outing, a new high` };
    case "close_call":
      return { title: "Close Call", why: "Won a game by two" };
  }
}

/** The calendar window that holds exactly this outing's games. */
export function outingWindow(recap: Pick<RecapSummary, "start" | "end">): { start: string; end: string } {
  return { start: recap.start, end: new Date(new Date(recap.end).getTime() + 1000).toISOString() };
}

/** "6 games · 5 players" */
export function outingSize(recap: Pick<RecapSummary, "games" | "players">): string {
  return `${plural(recap.games, "1 game", `${String(recap.games)} games`)} · ${plural(recap.players, "1 player", `${String(recap.players)} players`)}`;
}
