// Open crews (routes/open_crews.py, migration 0038): crews whose lead opened them, so anyone
// signed in can find them nearby and join at once. The listing never shows who's in a crew.

export const OPEN_FEATURE = "crew.open";
export const MEMBERS_MIN = 2;
export const MEMBERS_MAX = 100;
export const MEMBERS_DEFAULT = 12;
export const RADIUS_KM = 25;

export interface OpenCrew {
  group_id: string;
  name: string;
  about: string | null;
  usual_days: string[];
  usual_times: string[];
  // The crew's own name for its default court, and Google's ID for it (a public place).
  court: string;
  google_place_id: string;
  distance_km: number;
  members: number;
  max_members: number;
  full: boolean;
  // You're already in it, or waiting to be let in.
  my_status: "active" | "pending" | null;
}

export interface PlaceAnswer {
  outcome: "found" | "not_found" | "unavailable";
  crews: OpenCrew[];
}

/** Where Find searches from. Kept on this device only, never sent to be stored. */
export type Start = { kind: "here" } | { kind: "place"; placeId: string; label: string };

const START_KEY = "popshot.find.start";
const PLACE_ID = /^[A-Za-z0-9_-]{1,300}$/;

/** The remembered start, or null when there's none or storage can't be read. */
export function loadStart(storage: Pick<Storage, "getItem"> | null): Start | null {
  try {
    const raw = storage?.getItem(START_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as unknown;
    if (typeof value !== "object" || value === null) return null;
    const start = value as Record<string, unknown>;
    if (start.kind === "here") return { kind: "here" };
    if (
      start.kind === "place" &&
      typeof start.placeId === "string" &&
      PLACE_ID.test(start.placeId) &&
      typeof start.label === "string" &&
      start.label.length > 0 &&
      start.label.length <= 200
    ) {
      return { kind: "place", placeId: start.placeId, label: start.label };
    }
    return null;
  } catch {
    return null;
  }
}

/** Remember (or, with null, forget) the start on this device. Storage may refuse: that's fine. */
export function saveStart(storage: Pick<Storage, "setItem" | "removeItem"> | null, start: Start | null): void {
  try {
    if (start === null) {
      storage?.removeItem(START_KEY);
    } else {
      storage?.setItem(START_KEY, JSON.stringify(start));
    }
  } catch {
    // Private windows and blocked storage: Find just asks again next time.
  }
}

/** "Under 1 km", "3.4 km" or "18 km" away. */
export function distanceLabel(km: number): string {
  if (km < 1) return "Under 1 km";
  if (km < 10) return `${km.toFixed(1)} km`;
  return `${String(Math.round(km))} km`;
}

/** "Full", "1 spot left" or "7 of 12 players". */
export function spaceLabel(crew: Pick<OpenCrew, "members" | "max_members" | "full">): string {
  if (crew.full || crew.members >= crew.max_members) return "Full";
  const left = crew.max_members - crew.members;
  if (left === 1) return "1 spot left";
  return `${String(crew.members)} of ${String(crew.max_members)} players`;
}

export const REPORT_REASONS = [
  { value: "spam", label: "Spam or advertising" },
  { value: "unsafe", label: "Feels unsafe" },
  { value: "offensive", label: "Offensive name or words" },
  { value: "not_pickleball", label: "Not a pickleball crew" },
  { value: "other", label: "Something else" },
] as const;

export type ReportReason = (typeof REPORT_REASONS)[number]["value"];

/** What to say when the browser couldn't give a location. */
export function locationProblem(code: number | null): string {
  // GeolocationPositionError: 1 permission denied, 2 unavailable, 3 timeout.
  if (code === 1) return "Location is off for Popshot. Search for a town or park instead.";
  return "We couldn't get your location just now. Search for a town or park instead.";
}

/** What to say about a typed place Google couldn't use. */
export function placeProblem(outcome: PlaceAnswer["outcome"]): string | null {
  if (outcome === "not_found") return "Google Maps can't find that place any more. Search again.";
  if (outcome === "unavailable") return "Place search isn't working just now. Try your location instead.";
  return null;
}
