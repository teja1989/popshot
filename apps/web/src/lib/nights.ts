// Play nights. Shapes match the API's routes/nights.py.

export type Answer = "in" | "maybe" | "out";

export interface NightPerson {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
}

export interface Night {
  id: string;
  group_id: string;
  group_name: string;
  series_id: string | null;
  starts_at: string;
  venue: string;
  // The crew's saved court it's at (lib/courts.ts), and Google's ID for a Maps link.
  court_id?: string | null;
  court_google_place_id?: string | null;
  note: string | null;
  spots: number | null;
  created_by_name: string;
  cancelled: boolean;
  open: boolean;
  can_edit: boolean;
  going: NightPerson[];
  waitlist: NightPerson[];
  maybe: NightPerson[];
  out: NightPerson[];
  my_answer: Answer | null;
  my_waitlist_position: number | null;
}

export const ANSWERS: { value: Answer; label: string }[] = [
  { value: "in", label: "I'm in" },
  { value: "maybe", label: "Maybe" },
  { value: "out", label: "Can't go" },
];

export const VENUE_MAX = 80;
export const NOTE_MAX = 200;
export const MAX_WEEKS = 12;

/** "Thu 16 Oct · 6:00 PM", or "Today · 6:00 PM" / "Tomorrow · 6:00 PM", in the viewer's time zone. */
export function nightWhen(startsAt: string, now: Date = new Date(), locale?: string): string {
  const when = new Date(startsAt);
  const time = when.toLocaleTimeString(locale, { hour: "numeric", minute: "2-digit" });
  const day = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((day(when) - day(now)) / 86_400_000);
  if (days === 0) {
    return `Today · ${time}`;
  }
  if (days === 1) {
    return `Tomorrow · ${time}`;
  }
  const date = when.toLocaleDateString(locale, { weekday: "short", day: "numeric", month: "short" });
  return `${date} · ${time}`;
}

/** "5 going · 3 spots left", "Full · 2 waiting", "4 going". */
export function spotsLine(night: Pick<Night, "going" | "waitlist" | "spots">): string {
  const going = `${String(night.going.length)} going`;
  if (night.spots === null) {
    return going;
  }
  const left = night.spots - night.going.length;
  if (left > 0) {
    return `${going} · ${String(left)} ${left === 1 ? "spot" : "spots"} left`;
  }
  return night.waitlist.length > 0 ? `Full · ${String(night.waitlist.length)} waiting` : "Full";
}

/** What your answer means right now, e.g. "You're in" or "You're 2nd on the waitlist". */
export function myStatus(night: Pick<Night, "my_answer" | "my_waitlist_position">): string | null {
  if (night.my_waitlist_position !== null) {
    return `You're ${ordinal(night.my_waitlist_position)} on the waitlist`;
  }
  switch (night.my_answer) {
    case "in":
      return "You're in";
    case "maybe":
      return "You said maybe";
    case "out":
      return "You can't make it";
    default:
      return null;
  }
}

export function ordinal(n: number): string {
  const tens = n % 100;
  if (tens >= 11 && tens <= 13) {
    return `${String(n)}th`;
  }
  const suffix = ["th", "st", "nd", "rd"][n % 10] ?? "th";
  return `${String(n)}${suffix}`;
}

/** A sensible default start for a new night: tomorrow at 6pm, local time. */
export function defaultStart(now: Date = new Date()): Date {
  return new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1, 18, 0);
}
