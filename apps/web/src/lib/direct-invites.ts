// Direct invites: a lead or co-lead invites a person, who accepts or declines. Shapes match
// the API's routes/direct_invites.py.

export type Standing = "member" | "requested" | "invited";

export interface Person {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  standing: Standing | null;
}

export interface GroupDirectInvite {
  id: string;
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  invited_by_name: string | null;
  created_at: string;
  expires_at: string;
}

export interface MyInvite {
  id: string;
  group_id: string;
  group_name: string;
  invited_by_name: string | null;
  members: number;
  created_at: string;
  expires_at: string;
}

export interface InviteBlock {
  group_id: string;
  group_name: string;
  created_at: string;
}

export type InviteAnswer = "accept" | "decline" | "block";

export const STANDING_LABEL: Record<Standing, string> = {
  member: "In the crew",
  requested: "Asked to join",
  invited: "Invited",
};

// Crockford base32, as on the API: no I, L, O or U.
const CODE = /^[0-9A-HJKMNP-TV-Z]{8}$/;

/** A typed code as the API stores it ("k7m2 qx4p" → "K7M2QX4P"), or null if it can't be one. */
export function normalizeCode(typed: string): string | null {
  const code = typed.toUpperCase().replace(/[\s-]/g, "").replace(/O/g, "0").replace(/[IL]/g, "1");
  return CODE.test(code) ? code : null;
}

/** "Casey invited you · 4 members" */
export function inviteLine(invite: Pick<MyInvite, "invited_by_name" | "members">): string {
  const who = invite.invited_by_name ? `${invite.invited_by_name} invited you` : "You're invited";
  const members = invite.members === 1 ? "1 member" : `${String(invite.members)} members`;
  return `${who} · ${members}`;
}
