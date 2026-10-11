// The admin page. Shapes match the API's routes/admin.py.

export interface Totals {
  users: number;
  new_users_7d: number;
  active_users_7d: number;
  active_users_30d: number;
  live_groups: number;
  deleted_groups: number;
  games: number;
  games_30d: number;
  push_users: number;
  level_set: number;
}

export interface Week {
  week_start: string;
  active_users: number;
  new_users: number;
  active_crews: number;
  games: number;
  nights: number;
  answers: number;
}

export interface Cohort {
  cohort_week: string;
  signed_up: number;
  week_1: number;
  week_2: number;
  week_3: number;
  week_4: number;
}

export interface Overview {
  totals: Totals;
  // Oldest first.
  weeks: Week[];
  retention: Cohort[];
}

export interface AdminGroup {
  id: string;
  name: string;
  created_at: string;
  members: number;
  games: number;
  games_30d: number;
  last_game_at: string | null;
  upcoming_nights: number;
}

/** "40%" of `of`, "–" when there's nobody to count. */
export function share(count: number, of: number): string {
  return of === 0 ? "–" : `${String(Math.round((100 * count) / of))}%`;
}

/** "Oct 5" for a date (YYYY-MM-DD) or timestamp, in UTC so weeks line up with the API's. */
export function shortDate(value: string): string {
  return new Date(value.length === 10 ? `${value}T00:00:00Z` : value).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

/** Retention cells a cohort has had time to reach: week N needs N full weeks since signup. */
export function reachedWeeks(cohortWeek: string, now: Date): number {
  const start = new Date(`${cohortWeek}T00:00:00Z`).getTime();
  const weeks = Math.floor((now.getTime() - start) / (7 * 24 * 60 * 60 * 1000));
  return Math.max(0, Math.min(4, weeks));
}

export type Role = "lead" | "co_lead" | "member";
export type MemberStatus = "pending" | "active" | "removed";

export interface PersonRow {
  id: string;
  display_name: string;
  avatar_url: string | null;
  created_at: string;
  last_active: string | null;
  groups: number;
}

export interface PeopleResults {
  people: PersonRow[];
  // False when an email couldn't be looked up (Firebase unavailable here).
  email_search: boolean;
}

export interface PersonGroup {
  group_id: string;
  name: string;
  role: Role;
  status: MemberStatus;
  left_on_own: boolean;
  joined_at: string;
  deleted_at: string | null;
  games: number;
}

export interface Person {
  id: string;
  display_name: string;
  avatar_url: string | null;
  created_at: string;
  self_level: string | null;
  last_active: string | null;
  active_days_30: number;
  push_devices: number;
  email: string | null;
  last_sign_in: string | null;
  disabled: boolean | null;
  account: "found" | "missing" | "unavailable";
  groups: PersonGroup[];
}

export interface CrewMember {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  role: Role;
  status: MemberStatus;
  left_on_own: boolean;
  joined_at: string;
  games: number;
}

export interface Crew {
  id: string;
  name: string;
  created_at: string;
  created_by: string;
  deleted_at: string | null;
  members: number;
  pending: number;
  guests: number;
  games: number;
  last_game_at: string | null;
  upcoming_nights: number;
  open_invites: number;
  people: CrewMember[];
}

const ROLE_LABEL: Record<Role, string> = { lead: "Lead", co_lead: "Co-lead", member: "Member" };

/** "Lead", "Member", "Left", "Removed", "Asked to join". */
export function membership(m: { role: Role; status: MemberStatus; left_on_own: boolean }): string {
  if (m.status === "pending") {
    return "Asked to join";
  }
  if (m.status === "removed") {
    return m.left_on_own ? "Left" : "Removed";
  }
  return ROLE_LABEL[m.role];
}
