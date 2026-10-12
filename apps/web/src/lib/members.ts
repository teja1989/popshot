// The members page: a friendly line about each member, and the crew's guests. Shapes match
// the API's routes/groups.py and routes/guests.py.

export interface Guest {
  id: string;
  display_name: string;
  games: number;
}

const DAY_MS = 86_400_000;

/** "Played today", "Played yesterday", "Played 3 days ago", "Played in March". */
export function lastPlayed(at: string | null | undefined, now: Date = new Date(), locale?: string): string {
  if (!at) {
    return "No games yet";
  }
  const when = new Date(at);
  const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((startOfDay(now) - startOfDay(when)) / DAY_MS);
  if (days <= 0) {
    return "Played today";
  }
  if (days === 1) {
    return "Played yesterday";
  }
  if (days < 14) {
    return `Played ${String(days)} days ago`;
  }
  const sameYear = when.getFullYear() === now.getFullYear();
  const month = when.toLocaleDateString(locale, sameYear ? { month: "long" } : { month: "long", year: "numeric" });
  return `Played in ${month}`;
}

/** "Joined March 2026" */
export function joined(at: string | undefined, locale?: string): string | null {
  if (!at) {
    return null;
  }
  return `Joined ${new Date(at).toLocaleDateString(locale, { month: "long", year: "numeric" })}`;
}

/** "Joined March 2026 · Played 3 days ago" */
export function memberLine(
  member: { joined_at?: string; last_played_at?: string | null },
  now: Date = new Date(),
  locale?: string,
): string {
  return [joined(member.joined_at, locale), lastPlayed(member.last_played_at, now, locale)]
    .filter((part) => part !== null)
    .join(" · ");
}

export function gamesCount(games: number): string {
  return games === 1 ? "1 game" : `${String(games)} games`;
}
