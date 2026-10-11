// Shapes returned by the API's routes/games.py, and how games read on screen.

import type { Reflection } from "./focus";
import type { Format } from "./groups";
import type { BestOf, PointsTo, Team } from "./scoring";

export interface Player {
  id: string;
  display_name: string;
  avatar_url: string | null;
  user_id: string | null;
  is_guest: boolean;
  is_me: boolean;
}

export interface MatchPlayer {
  player_id: string;
  display_name: string;
  is_guest: boolean;
  team: Team;
}

export interface GameScore {
  team_a: number;
  team_b: number;
}

export interface Match {
  id: string;
  format: Format;
  points_to: PointsTo;
  win_by_two: boolean;
  best_of: BestOf;
  played_at: string;
  entered_by_name: string | null;
  entered_by_me: boolean;
  winner: Team;
  players: MatchPlayer[];
  games: GameScore[];
  i_played: boolean;
  // Whoever logged a game can edit or delete it.
  can_edit: boolean;
  // Yours only. Both lists empty means you skipped it.
  my_reflection: Reflection | null;
}

export interface LogGameBody {
  format: Format;
  points_to: PointsTo;
  win_by_two: boolean;
  best_of: BestOf;
  played_at?: string;
  team_a: string[];
  team_b: string[];
  games: GameScore[];
}

// Guests and your own name: the API allows up to 40 characters.
export const NAME_MAX = 40;

/** "Casey & Sam" */
export function teamNames(names: readonly string[]): string {
  return names.join(" & ");
}

export function namesOn(match: Pick<Match, "players">, team: Team): string {
  return teamNames(match.players.filter((p) => p.team === team).map((p) => p.display_name));
}

/** Scores from the winner's side: "11–7" or "11–7, 9–11, 11–8". */
export function scoreLine(match: Pick<Match, "games" | "winner">): string {
  return match.games
    .map((g) => (match.winner === "A" ? `${String(g.team_a)}–${String(g.team_b)}` : `${String(g.team_b)}–${String(g.team_a)}`))
    .join(", ");
}

/** "Today, 6:40 PM", "Yesterday, 9:05 AM" or "Sat 4 Oct, 10:00 AM", in the viewer's time zone. */
export function playedWhen(playedAt: string, now: Date = new Date(), locale?: string): string {
  const when = new Date(playedAt);
  const time = when.toLocaleTimeString(locale, { hour: "numeric", minute: "2-digit" });
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((startOfDay(now) - startOfDay(when)) / 86_400_000);
  if (days === 0) {
    return `Today, ${time}`;
  }
  if (days === 1) {
    return `Yesterday, ${time}`;
  }
  const date = when.toLocaleDateString(locale, { weekday: "short", day: "numeric", month: "short" });
  return `${date}, ${time}`;
}

/** A value for <input type="datetime-local"> in the viewer's time zone. */
export function toLocalInput(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${String(date.getFullYear())}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
