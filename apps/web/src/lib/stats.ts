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

export interface TimelinePoint {
  played_at: string;
  doubles: boolean;
  won: boolean;
  // Your crew points after this match.
  rating: number;
}

export type Window = 30 | 90 | null;

export const WINDOWS: { value: Window; label: string }[] = [
  { value: 30, label: "30 days" },
  { value: 90, label: "90 days" },
  { value: null, label: "All time" },
];

export interface MyStats {
  days: number | null;
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
  // Oldest first.
  timeline: TimelinePoint[];
  rating_start: number | null;
  rating_now: number | null;
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

/** The stats URL for a group and window. */
export function statsPath(groupId: string, days: Window): `/v1/${string}` {
  return `/v1/groups/${groupId}/stats/me${days ? `?days=${String(days)}` : ""}`;
}

const DAY_MS = 86_400_000;

/** Monday 00:00 of the week `date` falls in, in the viewer's time zone. */
export function weekStart(date: Date): Date {
  const start = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  start.setDate(start.getDate() - ((start.getDay() + 6) % 7));
  return start;
}

/**
 * Matches per week (Monday to Sunday, local time), oldest week first, ending with this week.
 * Covers the window, or for all time from your first game, at most `maxWeeks` weeks.
 */
export function weeklyCounts(
  timeline: Pick<TimelinePoint, "played_at">[],
  days: Window,
  now: Date = new Date(),
  maxWeeks = 26,
): { start: Date; count: number }[] {
  const thisWeek = weekStart(now);
  const first = timeline[0] ? weekStart(new Date(timeline[0].played_at)) : thisWeek;
  const fromWindow = days ? weekStart(new Date(now.getTime() - days * DAY_MS)) : first;
  // Weeks between two Mondays; rounding absorbs daylight-saving shifts.
  const span = Math.round((thisWeek.getTime() - fromWindow.getTime()) / (7 * DAY_MS));
  const weeks = Math.min(maxWeeks, span + 1);
  const result = Array.from({ length: weeks }, (_, i) => {
    const start = new Date(thisWeek);
    start.setDate(start.getDate() - 7 * (weeks - 1 - i));
    return { start, count: 0 };
  });
  for (const point of timeline) {
    const start = weekStart(new Date(point.played_at)).getTime();
    const bucket = result.find((w) => w.start.getTime() === start);
    if (bucket) {
      bucket.count += 1;
    }
  }
  return result;
}

const WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

/** The weekday you play most (local time), or null with no games. Ties go to earlier in the week. */
export function busiestDay(timeline: Pick<TimelinePoint, "played_at">[]): string | null {
  if (timeline.length === 0) {
    return null;
  }
  const counts = new Array<number>(7).fill(0);
  for (const point of timeline) {
    const day = new Date(point.played_at).getDay();
    counts[day] = (counts[day] ?? 0) + 1;
  }
  // Monday first, so a tie between Monday and Sunday goes to Monday.
  const order = [1, 2, 3, 4, 5, 6, 0];
  let best = order[0] ?? 1;
  for (const day of order) {
    if ((counts[day] ?? 0) > (counts[best] ?? 0)) {
      best = day;
    }
  }
  return WEEKDAYS[best] ?? null;
}

/** An SVG polyline for `values` in a `width` x `height` box, with `pad` around it. */
export function linePoints(values: number[], width: number, height: number, pad = 4): { x: number; y: number }[] {
  if (values.length === 0) {
    return [];
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  // A flat line sits in the middle rather than dividing by zero.
  const range = max - min || 1;
  const step = values.length > 1 ? (width - 2 * pad) / (values.length - 1) : 0;
  return values.map((v, i) => ({
    x: values.length > 1 ? pad + i * step : width / 2,
    y: max === min ? height / 2 : pad + ((max - v) / range) * (height - 2 * pad),
  }));
}
