// Head-to-head and fun stats. Shapes match the API's routes/stats.py.

import { teamNames } from "./games";

export interface PlayerRef {
  player_id: string;
  display_name: string;
  is_guest: boolean;
}

export interface RecordOut {
  player: PlayerRef;
  played: number;
  won: number;
}

export interface UpsetOut {
  match_id: string;
  played_at: string;
  winners: PlayerRef[];
  losers: PlayerRef[];
  gap: number;
}

export interface MyStats {
  matches: number;
  wins: number;
  current_streak: { result: "W" | "L"; length: number } | null;
  longest_win_streak: number;
  close_won: number;
  close_lost: number;
  skunks_given: number;
  skunks_taken: number;
  upset_wins: number;
  biggest_upset: UpsetOut | null;
  best_partner: RecordOut | null;
  nemesis: RecordOut | null;
  // Most matches first.
  head_to_head: RecordOut[];
  min_pairing: number;
}

export interface Highlights {
  longest_win_streak: { player: PlayerRef; length: number } | null;
  most_games: { player: PlayerRef; matches: number } | null;
  biggest_upset: UpsetOut | null;
  window_days: number;
}

/** "5–2": wins first. */
export function record(won: number, lost: number): string {
  return `${String(won)}–${String(lost)}`;
}

/** "Won 3 in a row", "Lost 1", or null before the first game. */
export function streakText(streak: MyStats["current_streak"]): string | null {
  if (!streak) {
    return null;
  }
  const verb = streak.result === "W" ? "Won" : "Lost";
  return streak.length === 1 ? `${verb} the last one` : `${verb} ${String(streak.length)} in a row`;
}

/** "Casey & Sam beat Riley & Alex" */
export function upsetLine(upset: UpsetOut): string {
  return `${teamNames(upset.winners.map((p) => p.display_name))} beat ${teamNames(upset.losers.map((p) => p.display_name))}`;
}

export function hasHighlights(h: Highlights): boolean {
  return h.longest_win_streak !== null || h.most_games !== null || h.biggest_upset !== null;
}
