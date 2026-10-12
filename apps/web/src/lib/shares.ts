// Shared recap links: a recap card anyone with the link can open, no sign-in needed. Shapes
// match the API's routes/shares.py.

import type { AwardKind } from "./recaps";

// secrets.token_urlsafe(32) on the API: 43 URL-safe characters.
export const SHARE_TOKEN = /^[A-Za-z0-9_-]{43}$/;
// Shown for people who'd rather not be named on shared cards.
export const HIDDEN_NAME = "Crew member";

export interface SharedNames {
  // First names that may be shown, and how many more people there were.
  names: string[];
  more: number;
}

export interface SharedRecap {
  crew: string;
  start: string;
  end: string;
  games: number;
  players: number;
  headline: string;
  lines: string[];
  written_by: "popshot" | "ai";
  newcomers: SharedNames;
  awards: (SharedNames & { kind: AwardKind; value: number })[];
  played: { name: string; games: number }[];
  matches: { team_a: string[]; team_b: string[]; games: [number, number][] }[];
  expires_at: string;
}

export interface NewShare {
  token: string;
  expires_at: string;
}

export interface ShareStatus {
  live: number;
  yours_to_turn_off: number;
}

/** "Ana, Bo and 2 more", or "2 crew members" when nobody can be named. */
export function namesText({ names, more }: SharedNames): string {
  if (names.length === 0) {
    return more === 1 ? "A crew member" : `${String(more)} crew members`;
  }
  if (more > 0) {
    return `${names.join(", ")} and ${String(more)} more`;
  }
  if (names.length === 1) {
    return names[0] ?? "";
  }
  return `${names.slice(0, -1).join(", ")} and ${names.at(-1) ?? ""}`;
}

/** The link to a shared recap on this site. */
export function shareUrl(origin: string, token: string): string {
  return new URL(`/r/${token}`, origin).toString();
}

/** "11–9, 8–11 and 11–6": a match's games, team A's points first. */
export function gamesText(games: [number, number][]): string {
  const each = games.map(([a, b]) => `${String(a)}–${String(b)}`);
  if (each.length <= 1) {
    return each[0] ?? "";
  }
  return `${each.slice(0, -1).join(", ")} and ${each.at(-1) ?? ""}`;
}

/** Whether team A won the match (more games won). */
export function teamAWon(games: [number, number][]): boolean {
  const aWins = games.filter(([a, b]) => a > b).length;
  return aWins * 2 > games.length;
}

const HOST = /^[a-z0-9.-]{1,253}(:[0-9]{1,5})?$/i;

/**
 * This site's origin, from the request (Cloud Run passes the host it was reached on), for the
 * absolute preview-image link chat apps need. Null if the headers look wrong.
 */
export function siteOrigin(headers: Headers): URL | null {
  const host = headers.get("x-forwarded-host") ?? headers.get("host");
  const proto = headers.get("x-forwarded-proto") ?? "https";
  if (!host || !HOST.test(host) || (proto !== "https" && proto !== "http")) {
    return null;
  }
  return new URL(`${proto}://${host}`);
}
