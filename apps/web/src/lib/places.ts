// A crew's court on the map, found with Google Places through our API (routes/places.py).
// We keep only Google's ID for the place and the crew's own name for it: Google's name and
// address can't be kept, so the lead types the name.

export const PLACES_FEATURE = "courts.places";

/** Searching starts at this many characters (the API's minimum) and waits for a pause in typing. */
export const SEARCH_MIN = 2;
export const SEARCH_MAX = 80;
export const SEARCH_PAUSE_MS = 350;

export interface PlaceSuggestion {
  place_id: string;
  main: string;
  secondary: string;
}

export interface SearchResult {
  suggestions: PlaceSuggestion[];
  // Google couldn't be reached.
  unavailable: boolean;
}

export type PickOutcome = "saved" | "not_found" | "unavailable";

/** What's worth sending to the search: trimmed, long enough, never longer than the API allows. */
export function searchText(typed: string): string | null {
  const text = typed.trim().slice(0, SEARCH_MAX);
  return text.length >= SEARCH_MIN ? text : null;
}

// Google's place IDs: letters, digits, '-' and '_' (the API checks the same).
const PLACE_ID = /^[A-Za-z0-9_-]{1,300}$/;

/** A Google Maps link to the place, or null for anything that isn't a place ID. */
export function mapsUrl(placeId: string | null | undefined, name: string | null | undefined): string | null {
  if (!placeId || !PLACE_ID.test(placeId)) {
    return null;
  }
  const named = name?.trim() ?? "";
  const query = new URLSearchParams({
    api: "1",
    query: named.length > 0 ? named : "Pickleball court",
    query_place_id: placeId,
  });
  return `https://www.google.com/maps/search/?${query.toString()}`;
}

/** What to say after a pick that didn't save. */
export function pickProblem(outcome: PickOutcome): string | null {
  switch (outcome) {
    case "saved":
      return null;
    case "not_found":
      return "Google Maps can't find that place any more. Search again.";
    case "unavailable":
      return "Court search isn't working just now. Try again in a little while.";
  }
}

/** A new Google session: the keystrokes and the pick that follows are billed as one. */
export function newSession(random: () => string = () => crypto.randomUUID()): string {
  return random();
}
