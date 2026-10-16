// A crew's saved courts (API: routes/courts.py, ADR 0007): up to 5, typed or found on Google
// Maps, one of them the default. Meetups pick from them, default first.

import { mapsUrl } from "./places";

export const COURTS_MAX = 5;

export interface Court {
  id: string;
  // The crew's own name for it.
  label: string;
  // Set when it was found on Google Maps.
  google_place_id: string | null;
  is_default: boolean;
}

/** Default first, then the crew's order. */
export function inOrder(courts: readonly Court[]): Court[] {
  return [...courts].sort((a, b) => Number(b.is_default) - Number(a.is_default));
}

/** A Google Maps link for a court found on Google, else null. */
export function courtMapsUrl(court: Pick<Court, "label" | "google_place_id">): string | null {
  return mapsUrl(court.google_place_id, court.label);
}

/** Where a meetup is: one of the crew's courts, or somewhere typed. */
export type Where = { kind: "court"; court: Court } | { kind: "elsewhere"; venue: string };

/** What the meetup sheet starts with. A meetup being changed keeps its court if the crew
 *  still has it; a new one starts at the default court, else where the crew played last. */
export function initialWhere(
  courts: readonly Court[],
  editing: { venue: string; court_id?: string | null } | undefined,
  lastVenue: string | undefined,
): Where {
  if (editing) {
    const court = courts.find((c) => c.id === editing.court_id);
    return court ? { kind: "court", court } : { kind: "elsewhere", venue: editing.venue };
  }
  const preferred = courts.find((c) => c.is_default);
  return preferred ? { kind: "court", court: preferred } : { kind: "elsewhere", venue: lastVenue ?? "" };
}

/** The venue text and court a meetup is saved with. */
export function wherePayload(where: Where): { venue: string; court_id: string | null } {
  return where.kind === "court"
    ? { venue: where.court.label, court_id: where.court.id }
    : { venue: where.venue.trim(), court_id: null };
}
