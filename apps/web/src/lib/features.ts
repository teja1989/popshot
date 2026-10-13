// What's switched on for you (migration 0027, GET /v1/me/features). The app only uses this to
// hide or show things; the API decides for real on every request.

export interface MyFeatures {
  // What's on in each of your crews.
  crews: Record<string, string[]>;
  // What's on in at least one of them.
  everywhere: string[];
}

export const NO_FEATURES: MyFeatures = { crews: {}, everywhere: [] };

/** Is `key` on for this crew? Prefix keys ending in ".*" match any feature under them. */
export function featureOn(features: MyFeatures, key: string, crewId: string | null): boolean {
  if (crewId === null) {
    return false;
  }
  const on = features.crews[crewId] ?? [];
  if (key.endsWith(".*")) {
    const prefix = key.slice(0, -1);
    return on.some((k) => k.startsWith(prefix));
  }
  return on.includes(key);
}

// How often to look again while the app stays open (it also looks when you come back to it).
export const REFRESH_MS = 5 * 60 * 1000;
