// A crew's profile: a short "about", usual days and times, home courts. Shapes match the
// API's routes/groups.py. Home courts are for members only; previews don't have them.

export type Day = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun";
export type TimeOfDay = "morning" | "midday" | "evening";

export const DAYS: readonly Day[] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
export const TIMES: readonly TimeOfDay[] = ["morning", "midday", "evening"];

export const DAY_LABEL: Record<Day, string> = {
  mon: "Mon",
  tue: "Tue",
  wed: "Wed",
  thu: "Thu",
  fri: "Fri",
  sat: "Sat",
  sun: "Sun",
};

export const TIME_LABEL: Record<TimeOfDay, { one: string; many: string }> = {
  morning: { one: "Morning", many: "mornings" },
  midday: { one: "Midday", many: "middays" },
  evening: { one: "Evening", many: "evenings" },
};

export const ABOUT_MAX = 200;
export const COURT_MAX = 80;

export interface CrewProfile {
  about: string | null;
  usual_days: Day[];
  usual_times: TimeOfDay[];
}

function and(parts: string[]): string {
  if (parts.length <= 1) {
    return parts[0] ?? "";
  }
  return `${parts.slice(0, -1).join(", ")} and ${parts.at(-1) ?? ""}`;
}

/** "Usually Tue, Thu and Sat · mornings and evenings", or null when nothing is set. */
export function usualLine(profile: Pick<CrewProfile, "usual_days" | "usual_times">): string | null {
  const days = DAYS.filter((d) => profile.usual_days.includes(d));
  const times = TIMES.filter((t) => profile.usual_times.includes(t));
  if (days.length === 0 && times.length === 0) {
    return null;
  }
  const dayText = days.length === 7 ? "every day" : and(days.map((d) => DAY_LABEL[d]));
  const timeText = and(times.map((t) => TIME_LABEL[t].many));
  if (days.length === 0) {
    return `Usually ${timeText}`;
  }
  return times.length === 0 ? `Usually ${dayText}` : `Usually ${dayText} · ${timeText}`;
}

// Same rule as the API (routes/groups.py): no links, web or email addresses.
const LINK =
  /https?:\/\/|www\.|[\w.%+-]+@[\w-]+\.[a-z]|\b[\w-]+\.(com|net|org|io|app|co|ly|me|gg|xyz|info|biz|link|site)\b/i;

export function hasLink(text: string): boolean {
  return LINK.test(text);
}
