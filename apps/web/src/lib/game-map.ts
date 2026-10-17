// Your game map on You (docs/game-map.md): your rhythm against your own goal, and your form
// against what crew points expected. Shapes match the API's routes/game_map.py. Only ever
// about you: there's no one else on it.

import { edgeText } from "./board";

export const MAP_FEATURE = "you.map";
// Form is drawn within ±FORM_LIMIT (a share of points); anything beyond sits on the edge.
export const FORM_LIMIT = 0.15;
export const GOAL_MIN = 1;
export const GOAL_MAX = 14;

export type Box = "in_the_groove" | "sharp_play_more" | "building" | "getting_going";

export interface MapPoint {
  ending: string;
  games: number;
  per_week: number;
  form: number | null;
  box: Box | null;
}

export interface GameMap {
  goal: number;
  goal_set: boolean;
  min_games: number;
  window_days: number;
  points: MapPoint[];
  crews: { group_id: string; name: string }[];
  partners: { group_id: string; player: { player_id: string; display_name: string }; games: number }[];
}

export interface BoxCopy {
  title: string;
  means: string;
  next: { label: string; href: string };
}

/** No box is a bad one: each says what it means and offers one next step. */
export const BOXES: Record<Box, BoxCopy> = {
  in_the_groove: {
    title: "In the groove",
    means: "Playing often, and your results are ahead of what was expected.",
    next: { label: "Share a recap with friends", href: "/crew" },
  },
  sharp_play_more: {
    title: "Sharp, play more",
    means: "Your results are ahead of expected. A few more games a week would build on it.",
    next: { label: "Find a meetup this week", href: "/play" },
  },
  building: {
    title: "Building",
    means: "Lots of games, and your results are catching up.",
    next: { label: "Pick one thing to work on", href: "/you/journey" },
  },
  getting_going: {
    title: "Getting going",
    means: "Fewer games for now, and your results are still to come.",
    next: { label: "Join a meetup this week", href: "/play" },
  },
};

/** Where the boxes sit on the chart, for their corner labels. */
export const BOX_CORNERS: Record<Box, { right: boolean; top: boolean }> = {
  in_the_groove: { right: true, top: true },
  sharp_play_more: { right: false, top: true },
  building: { right: true, top: false },
  getting_going: { right: false, top: false },
};

const clamp = (value: number) => Math.min(1, Math.max(0, value));

/** Left to right, 0 to 1: no games at the left edge, your goal in the middle, twice it at the right. */
export function rhythmPosition(perWeek: number, goal: number): number {
  return clamp(perWeek / (2 * goal));
}

/** Bottom to top, 0 to 1: as expected in the middle, ±FORM_LIMIT at the edges. */
export function formPosition(form: number): number {
  return clamp(0.5 + form / (2 * FORM_LIMIT));
}

function gamesAWeek(perWeek: number): string {
  const rounded = Math.round(perWeek * 10) / 10;
  return `${String(rounded)} game${rounded === 1 ? "" : "s"} a week`;
}

/** "Week to 17 Oct" */
export function weekLabel(ending: string): string {
  const day = new Date(ending).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  return `Week to ${day}`;
}

/** One point in words, for its tooltip, table row and screen readers. */
export function describePoint(point: MapPoint): string {
  if (point.form === null) {
    return `${gamesAWeek(point.per_week)}; not enough games yet to read results`;
  }
  return `${gamesAWeek(point.per_week)}, ${edgeText(point.form)}`;
}

/** The map in one line: "You're in the groove: 2.5 games a week, …". */
export function mapSummary(map: GameMap): string {
  const now = map.points.at(-1);
  if (!now?.box) {
    return `A few more games and your map appears. It needs ${String(map.min_games)} games in ${String(map.window_days)} days.`;
  }
  return `${BOXES[now.box].title}: ${describePoint(now)}.`;
}

/** Points that have a place on the chart (enough games for form), oldest first. */
export function plotted(map: GameMap): (MapPoint & { form: number; box: Box })[] {
  return map.points.filter((p): p is MapPoint & { form: number; box: Box } => p.form !== null && p.box !== null);
}
