// What's switched on for you (migration 0027, GET /v1/me/features). The app only uses this to
// hide or show things; the API decides for real on every request.

export interface MyFeatures {
  // What's on in each of your crews.
  crews: Record<string, string[]>;
  // What's on in at least one of them.
  everywhere: string[];
  // Switches in the 'you' area, which are per person, not per crew (migration 0032). Older
  // answers may not have it.
  you?: string[];
}

export const NO_FEATURES: MyFeatures = { crews: {}, everywhere: [], you: [] };

/** Is this 'you' switch on for you? Prefix keys ending in ".*" match any under them. */
export function youOn(features: MyFeatures, key: string): boolean {
  const on = features.you ?? [];
  if (key.endsWith(".*")) {
    const prefix = key.slice(0, -1);
    return on.some((k) => k.startsWith(prefix));
  }
  return on.includes(key);
}

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
