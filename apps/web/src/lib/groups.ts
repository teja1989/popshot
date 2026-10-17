// Shapes returned by the API's /v1/groups endpoints (services/api/.../routes/groups.py).

import type { Court } from "./courts";
import type { Day, TimeOfDay } from "./crew-profile";

export type Role = "lead" | "co_lead" | "member";
export type MemberStatus = "active" | "pending";
export type Format = "doubles" | "singles";
export type PointsTo = 11 | 15 | 21;

export interface MemberPreview {
  display_name: string;
  avatar_url: string | null;
}

export interface GroupSummary {
  id: string;
  name: string;
  my_role: Role;
  my_status: MemberStatus;
  member_count: number | null;
  // Up to 4 active members, the lead first.
  member_preview: MemberPreview[];
  // Games logged in the group, and how many you played. Null while you're waiting to join.
  games_logged: number | null;
  my_games: number | null;
}

export interface Member {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  role: Role;
  status: MemberStatus;
  // When they first joined (or asked to), and their latest game here.
  joined_at?: string;
  last_played_at?: string | null;
}

export interface FormerMember {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  // When they were removed or declined.
  since: string;
}

export interface GroupDetail extends GroupSummary {
  // The crew profile (lib/crew-profile.ts). Home courts are empty unless you're a member.
  about?: string | null;
  usual_days?: Day[];
  usual_times?: TimeOfDay[];
  // The crew's saved courts (lib/courts.ts), default included. Members only.
  courts?: Court[];
  default_format: Format;
  default_points_to: PointsTo;
  default_win_by_two: boolean;
  created_at: string;
  // Its days follow this clock (lib/time-zone.ts). Null until a lead's browser sends it.
  time_zone?: string | null;
  members: Member[];
  // Leads and co-leads only: people removed or declined, who can be restored.
  former_members: FormerMember[];
  // Open crews (lib/open-crews.ts): anyone signed in can find the crew and join, up to
  // max_members. Unlisted: Popshot's staff took it off the listing. Closed for court: it
  // closed because its default court stopped being one from the map.
  open_to_all?: boolean;
  max_members?: number;
  unlisted?: boolean;
  closed_for_court?: boolean;
}

export interface DeletedGroup {
  id: string;
  name: string;
  deleted_at: string;
  restorable_until: string;
}

/** "29 days", "1 day" or "less than a day" left to restore a deleted group. */
export function timeLeft(until: string, now: Date = new Date()): string {
  const left = new Date(until).getTime() - now.getTime();
  if (left < 86_400_000) {
    return "less than a day";
  }
  // Rounded up, so a group deleted a minute ago shows the full 30 days.
  const days = Math.ceil(left / 86_400_000);
  return days === 1 ? "1 day" : `${String(days)} days`;
}

export const ROLE_LABEL: Record<Role, string> = {
  lead: "Lead",
  co_lead: "Co-lead",
  member: "Member",
};

export function describeRules(
  group: Pick<GroupDetail, "default_format" | "default_points_to" | "default_win_by_two">,
): string {
  const format = group.default_format === "doubles" ? "Doubles" : "Singles";
  const winBy = group.default_win_by_two ? ", win by 2" : "";
  return `${format} · games to ${String(group.default_points_to)}${winBy}`;
}

export const GROUP_NAME_MAX = 60;
