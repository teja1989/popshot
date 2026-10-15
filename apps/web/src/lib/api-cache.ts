// What the app last heard from the API, kept in memory while the app is open, so a page you
// come back to shows straight away and refreshes quietly (stale-while-revalidate).
//
// Memory only: nothing is written to the device, and it's gone when the tab closes or you
// sign out. Entries are per signed-in account, so one person never sees another's data on a
// shared phone. Admin answers are never kept: admin pages always show what's live.

const MAX_ENTRIES = 150;

const entries = new Map<string, unknown>();

export function cacheKey(uid: string, path: string): string {
  return `${uid}\n${path}`;
}

export function cacheable(path: string): boolean {
  return !/^\/v1\/admin(\/|$|\?)/.test(path);
}

export function readCache(key: string): { data: unknown } | null {
  if (!entries.has(key)) {
    return null;
  }
  const data = entries.get(key);
  // Most recently used last, so the oldest goes first when full.
  entries.delete(key);
  entries.set(key, data);
  return { data };
}

export function writeCache(key: string, data: unknown): void {
  entries.delete(key);
  entries.set(key, data);
  while (entries.size > MAX_ENTRIES) {
    const oldest = entries.keys().next().value;
    if (oldest === undefined) {
      break;
    }
    entries.delete(oldest);
  }
}

export function forget(key: string): void {
  entries.delete(key);
}

/** On sign-out (or a different account signing in): forget everything. */
export function clearCache(): void {
  entries.clear();
}

export function cacheSize(): number {
  return entries.size;
}
