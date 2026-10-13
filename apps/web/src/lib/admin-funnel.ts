// The admin Funnel page. Shapes match the API's routes/admin_funnel.py.

import type { Source } from "./funnel";

export interface CrewFunnel {
  created: number;
  second_member: number;
  first_game: number;
  activated: number;
  week_2_eligible: number;
  played_week_2: number;
  week_4_eligible: number;
  played_week_4: number;
  median_hours_to_first_game: number | null;
}

export interface PeopleFunnel {
  signed_up: number;
  in_crew: number;
  played: number;
  week_2_eligible: number;
  back_week_2: number;
}

export interface SourceRow {
  source: Source;
  visits: number;
  signed_up: number;
  in_crew: number;
  played: number;
}

export interface Loops {
  recaps_shared: number;
  share_views: number;
  try_taps: number;
  recap_signups: number;
  invite_links: number;
  link_joins: number;
  direct_invites: number;
  direct_accepted: number;
  invite_signups: number;
  code_signups: number;
  active_users: number;
}

export type Stage = "deleted" | "needs_member" | "needs_first_game" | "quiet" | "activated" | "getting_going";

export interface CrewStage {
  id: string;
  name: string;
  created_at: string;
  members: number;
  games: number;
  games_first_week: number;
  first_game_at: string | null;
  last_game_at: string | null;
  stage: Stage;
}

export interface Funnel {
  weeks: number;
  since: string;
  crews: CrewFunnel;
  people: PeopleFunnel;
  sources: SourceRow[];
  loops: Loops;
  stages: CrewStage[];
  // Oldest first.
  active_crews: { week_start: string; active_crews: number }[];
}

export const PERIODS = [4, 8, 12] as const;

/** One bar of a funnel: how many reached the step, out of how many could have. */
export interface Step {
  label: string;
  count: number;
  of: number;
  note?: string;
}

export function crewSteps(c: CrewFunnel): Step[] {
  return [
    { label: "Started", count: c.created, of: c.created },
    { label: "A second member, first week", count: c.second_member, of: c.created },
    { label: "A first game, first week", count: c.first_game, of: c.created },
    { label: "3+ games, first week", count: c.activated, of: c.created },
    {
      label: "Played in week 2",
      count: c.played_week_2,
      of: c.week_2_eligible,
      note: `of ${String(c.week_2_eligible)} old enough`,
    },
    {
      label: "Played in week 4",
      count: c.played_week_4,
      of: c.week_4_eligible,
      note: `of ${String(c.week_4_eligible)} old enough`,
    },
  ];
}

export function peopleSteps(p: PeopleFunnel): Step[] {
  return [
    { label: "Signed up", count: p.signed_up, of: p.signed_up },
    { label: "In a crew, first week", count: p.in_crew, of: p.signed_up },
    { label: "Played, first 2 weeks", count: p.played, of: p.signed_up },
    {
      label: "Back in week 2",
      count: p.back_week_2,
      of: p.week_2_eligible,
      note: `of ${String(p.week_2_eligible)} old enough`,
    },
  ];
}

/** 0–100 for a bar's width. */
export function percent(count: number, of: number): number {
  return of === 0 ? 0 : Math.min(100, Math.round((100 * count) / of));
}

/** "about 6 hours", "about 2 days", or "no first games yet". */
export function waitText(hours: number | null): string {
  if (hours === null) {
    return "no first games yet";
  }
  if (hours < 1) {
    return "under an hour";
  }
  if (hours < 48) {
    return `about ${String(Math.round(hours))} hour${Math.round(hours) === 1 ? "" : "s"}`;
  }
  return `about ${String(Math.round(hours / 24))} days`;
}

/** New players who came from a share, an invite or a code, per person active in the period. */
export function spreadPerActive(l: Loops): string {
  if (l.active_users === 0) {
    return "–";
  }
  return ((l.recap_signups + l.invite_signups + l.code_signups) / l.active_users).toFixed(2);
}

export const STAGE_LABEL: Record<Stage, string> = {
  needs_member: "Needs a second member",
  needs_first_game: "Needs a first game",
  getting_going: "Getting going",
  activated: "Off to a great start",
  quiet: "Gone quiet (2+ weeks)",
  deleted: "Deleted",
};

export const SOURCE_LABEL: Record<Source, string> = {
  direct: "Direct (no tag)",
  recap: "Shared recap",
  invite: "Invite link",
  code: "Popshot code",
  reddit: "Reddit",
  facebook: "Facebook",
  nextdoor: "Nextdoor",
  poster: "Poster",
  court: "Court page",
  partner: "Partner",
  other: "Other tag",
};
