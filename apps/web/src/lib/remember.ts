// Small per-device preferences (which view a page shows). Storage can be missing or
// blocked (private windows, tests), so reading falls back and writing never throws.

export function recall<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const value = localStorage.getItem(key);
    return allowed.find((a) => a === value) ?? fallback;
  } catch {
    return fallback;
  }
}

export function remember(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Not remembered; the choice still applies for now.
  }
}
