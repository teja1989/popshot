// Invite links. The token travels in the URL fragment (/join#<token>): browsers never send
// the fragment to a server, so it stays out of request logs and Referer headers.
// Shapes match the API's routes/invites.py.

export const INVITE_PATH = "/join";
export const INVITE_DAYS = 7;
export const MAX_INVITE_USES = 10;
export const INVITE_USE_CHOICES = [1, 5, 10] as const;

// secrets.token_urlsafe(32) on the API: 43 URL-safe characters.
const TOKEN = /^[A-Za-z0-9_-]{43}$/;

export interface Invite {
  id: string;
  created_by_name: string | null;
  max_uses: number;
  use_count: number;
  expires_at: string;
  created_at: string;
}

export interface NewInvite extends Invite {
  token: string;
}

export type JoinStatus = "active" | "pending" | "removed";

export interface InvitePreview {
  group_name: string;
  invited_by: string;
  group_id: string | null;
  my_status: JoinStatus | null;
}

export interface Joined {
  group_id: string | null;
  status: JoinStatus;
}

export type MemberAction = "approve" | "decline" | "make_co_lead" | "make_member" | "remove";

export function inviteUrl(origin: string, token: string): string {
  return `${origin}${INVITE_PATH}#${token}`;
}

/** The token from a location hash like "#abc…", or null if it isn't one. */
export function tokenFromHash(hash: string): string | null {
  const token = hash.startsWith("#") ? hash.slice(1) : hash;
  return TOKEN.test(token) ? token : null;
}

export function describeUses(invite: Pick<Invite, "max_uses">): string {
  return invite.max_uses === 1 ? "For 1 person" : `For up to ${String(invite.max_uses)} people`;
}

export function describeJoined(invite: Pick<Invite, "use_count">): string {
  return invite.use_count === 1 ? "1 joined" : `${String(invite.use_count)} joined`;
}

/** "Expires in 7 days", "Expires in 1 day", "Expires in 5 hours" or "Expires within the hour". */
export function describeExpiry(expiresAt: string, now: Date = new Date()): string {
  const ms = new Date(expiresAt).getTime() - now.getTime();
  const hours = Math.ceil(ms / 3_600_000);
  if (hours <= 1) {
    return "Expires within the hour";
  }
  if (hours < 24) {
    return `Expires in ${String(hours)} hours`;
  }
  const days = Math.round(ms / 86_400_000);
  return days === 1 ? "Expires in 1 day" : `Expires in ${String(days)} days`;
}
