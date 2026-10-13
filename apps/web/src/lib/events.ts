// Crew events: Dink Shuffle and Ride the River. Shapes match the API's routes/events.py.

import type { GameScore } from "./games";
import type { BestOf, PointsTo, Team } from "./scoring";

export type EventKind = "shuffle" | "river";
export type Vibe = "social" | "competitive";
export type Seeding = "random" | "crew_points" | "level";

export interface EventPlayer {
  player_id: string;
  display_name: string;
  is_guest: boolean;
  is_me: boolean;
  // False once they've left the event.
  here: boolean;
}

export interface EventCourt {
  court: number;
  team_a: string[];
  team_b: string[];
  match_id: string | null;
  games: GameScore[];
  winner: Team | null;
  skipped: boolean;
}

export interface EventRound {
  number: number;
  courts: EventCourt[];
  sitting_out: string[];
}

export interface Standing {
  player_id: string;
  games: number;
  wins: number;
  points_for: number;
  points_against: number;
}

export interface EventSummary {
  id: string;
  kind: EventKind;
  name: string;
  vibe: Vibe;
  status: "live" | "finished";
  created_at: string;
  rounds: number;
  players: number;
}

export interface CrewEvent extends EventSummary {
  points_to: PointsTo;
  win_by_two: boolean;
  best_of: BestOf;
  courts: number;
  night_id: string | null;
  people: EventPlayer[];
  round_list: EventRound[];
  can_manage: boolean;
  can_start_round: boolean;
  standings: Standing[] | null;
  mine: { games: number; wins: number } | null;
}

export interface NewEventBody {
  kind: EventKind;
  name: string;
  vibe: Vibe;
  players: string[];
  courts: number;
  points_to: PointsTo;
  win_by_two: boolean;
  best_of: BestOf;
  night_id: string | null;
  seeding: Seeding | null;
}

export const MIN_PLAYERS = 4;
export const MAX_PLAYERS = 24;
export const MAX_COURTS = 6;
export const NAME_MAX = 60;

export interface FormatInfo {
  kind: EventKind;
  // The playful name, and the standard one people already know.
  name: string;
  standard: string;
  blurb: string;
  // The switch that turns it on (migration 0028).
  feature: string;
}

export const FORMATS: readonly FormatInfo[] = [
  {
    kind: "shuffle",
    name: "Dink Shuffle",
    standard: "Round robin, rotating partners",
    blurb: "A new partner every round, and everyone sits out fairly. Great for mixing up the crew.",
    feature: "events.shuffle",
  },
  {
    kind: "river",
    name: "Ride the River",
    standard: "Up and down the river",
    blurb: "Winners move up a court, losers move down, and partners split every round.",
    feature: "events.river",
  },
];

export const SEEDING_LABEL: Record<Seeding, string> = {
  random: "At random",
  crew_points: "By crew points",
  level: "By level",
};

export function formatInfo(kind: EventKind): FormatInfo {
  const found = FORMATS.find((f) => f.kind === kind);
  if (!found) {
    throw new Error(`Unknown format ${kind}`);
  }
  return found;
}

/** Courts in use, and how many play and sit out each round. */
export function roundShape(players: number, courts: number): { courts: number; playing: number; sittingOut: number } {
  const used = Math.max(0, Math.min(courts, Math.floor(players / 4)));
  return { courts: used, playing: used * 4, sittingOut: players - used * 4 };
}

/** "8 play each round on 2 courts, 1 sits out." */
export function shapeLine(players: number, courts: number): string {
  if (players < MIN_PLAYERS) {
    return `Pick at least ${String(MIN_PLAYERS)} players.`;
  }
  const shape = roundShape(players, courts);
  const where = `${String(shape.playing)} play each round on ${String(shape.courts)} ${shape.courts === 1 ? "court" : "courts"}`;
  if (shape.sittingOut === 0) {
    return `${where}, nobody sits out.`;
  }
  return `${where}, ${String(shape.sittingOut)} ${shape.sittingOut === 1 ? "sits" : "sit"} out.`;
}

// A doubles game to 11 takes about this long, best of 1.
export const MINUTES_PER_GAME = 15;

/** About how many rounds fit in `minutes`. */
export function roundsIn(minutes: number, bestOf: BestOf = 1): number {
  const perRound = MINUTES_PER_GAME * (bestOf === 1 ? 1 : bestOf === 3 ? 2.5 : 4);
  return Math.max(1, Math.floor(minutes / perRound));
}

/**
 * "Suggest for us": a format that suits who's here. Ride the River needs at least two full
 * courts to move between; otherwise Dink Shuffle. Only formats that are switched on count.
 */
export function suggestFormat(
  players: number,
  courts: number,
  available: readonly EventKind[],
): { kind: EventKind; why: string } | null {
  if (available.length === 0) {
    return null;
  }
  const shape = roundShape(players, courts);
  if (available.includes("river") && shape.courts >= 2) {
    return {
      kind: "river",
      why: `With ${String(shape.courts)} courts in use, winners have somewhere to move up to.`,
    };
  }
  if (available.includes("shuffle")) {
    return {
      kind: "shuffle",
      why:
        shape.courts >= 2 || !available.includes("river")
          ? "Everyone partners someone new each round."
          : "With one court, rotating partners keeps it fresh.",
    };
  }
  return { kind: available[0] ?? "shuffle", why: "It's the one switched on for your crew." };
}

/** Whether the score boxes can start a court's game: the next unscored, unskipped court. */
export function openCourts(round: EventRound): EventCourt[] {
  return round.courts.filter((c) => c.match_id === null && !c.skipped);
}

/** "11–7" or "11–9, 8–11, 11–6". */
export function scoreText(games: readonly GameScore[]): string {
  return games.map((g) => `${String(g.team_a)}–${String(g.team_b)}`).join(", ");
}

/** "Ana & Bo". */
export function teamLine(ids: readonly string[], names: ReadonlyMap<string, string>): string {
  return ids.map((id) => names.get(id) ?? "Someone").join(" & ");
}

/** "+12", "−3", "0": points for minus against. */
export function pointDifference(s: Pick<Standing, "points_for" | "points_against">): string {
  const diff = s.points_for - s.points_against;
  return diff > 0 ? `+${String(diff)}` : diff < 0 ? `−${String(-diff)}` : "0";
}
