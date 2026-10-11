// Crew points and the Board. Shapes match the API's routes/board.py.

export interface BoardRow {
  player_id: string;
  display_name: string;
  avatar_url: string | null;
  is_guest: boolean;
  is_me: boolean;
  rating: number;
  reliability: number;
  matches: number;
  wins: number;
  // Most recent first.
  form: ("W" | "L")[];
  week_change: number | null;
  rank: number | null;
  to_go: number;
}

export interface Board {
  ranked: BoardRow[];
  getting_started: BoardRow[];
  resting: BoardRow[];
  ranked_after: number;
  resting_after_days: number;
}

export interface MyRating {
  group_id: string;
  group_name: string;
  rating: number;
  matches: number;
  rank: number | null;
  ranked_of: number;
  to_go: number;
}

export type Level = "beginner" | "intermediate" | "advanced" | "expert";

// Where crew points start for each self-rated level (popshot_api.rating.LEVEL_START).
export const LEVELS: { value: Level; label: string; start: number; hint: string }[] = [
  { value: "beginner", label: "Beginner", start: 2.5, hint: "Learning the rules and the kitchen" },
  { value: "intermediate", label: "Intermediate", start: 3.25, hint: "Steady rallies, working on drops" },
  { value: "advanced", label: "Advanced", start: 4.0, hint: "Resets, speed-ups, consistent thirds" },
  { value: "expert", label: "Expert", start: 4.75, hint: "Tournament-level play" },
];
export const DEFAULT_START = 3.0;

/** "3.47" */
export function points(value: number): string {
  return value.toFixed(2);
}

/** "▲ 0.12", "▼ 0.05", or null when there's nothing to show. */
export function change(value: number | null): { text: string; up: boolean } | null {
  if (value === null || Math.abs(value) < 0.005) {
    return null;
  }
  return { text: `${value > 0 ? "▲" : "▼"} ${Math.abs(value).toFixed(2)}`, up: value > 0 };
}

/** "72%" of matches won, or "–" with none. */
export function winRate(row: Pick<BoardRow, "wins" | "matches">): string {
  return row.matches === 0 ? "–" : `${String(Math.round((100 * row.wins) / row.matches))}%`;
}

export function levelLabel(level: string | null | undefined): string | null {
  return LEVELS.find((l) => l.value === level)?.label ?? null;
}
