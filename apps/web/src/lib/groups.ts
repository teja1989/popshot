// Shapes returned by the API's /v1/groups endpoints (services/api/.../routes/groups.py).

export type Role = "lead" | "co_lead" | "member";
export type MemberStatus = "active" | "pending";
export type Format = "doubles" | "singles";
export type PointsTo = 11 | 15 | 21;

export interface GroupSummary {
  id: string;
  name: string;
  my_role: Role;
  my_status: MemberStatus;
  member_count: number | null;
}

export interface Member {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  role: Role;
  status: MemberStatus;
}

export interface GroupDetail extends GroupSummary {
  default_format: Format;
  default_points_to: PointsTo;
  default_win_by_two: boolean;
  created_at: string;
  members: Member[];
}

export const ROLE_LABEL: Record<Role, string> = {
  lead: "Lead",
  co_lead: "Co-lead",
  member: "Member",
};

export function describeRules(group: Pick<GroupDetail, "default_format" | "default_points_to" | "default_win_by_two">): string {
  const format = group.default_format === "doubles" ? "Doubles" : "Singles";
  const winBy = group.default_win_by_two ? ", win by 2" : "";
  return `${format} · games to ${String(group.default_points_to)}${winBy}`;
}

export const GROUP_NAME_MAX = 60;
