// The Games tab's calendar: which days a week or month shows, in the viewer's own time
// zone, and which day each game or night falls on. Weeks start on Sunday.

export type Span = "week" | "month";

/** "2026-10-12" for the viewer's local day. */
export function dayKey(date: Date): string {
  const y = String(date.getFullYear());
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function startOfDay(date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate());
}

function addDays(date: Date, days: number): Date {
  // Calendar days, not 24-hour steps, so a clock change doesn't skip or repeat a day.
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
}

function startOfWeek(date: Date): Date {
  const day = startOfDay(date);
  return addDays(day, -day.getDay());
}

/** The days shown: one week, or whole weeks covering the month. */
export function daysShown(span: Span, anchor: Date): Date[] {
  if (span === "week") {
    const first = startOfWeek(anchor);
    return Array.from({ length: 7 }, (_, i) => addDays(first, i));
  }
  const first = startOfWeek(new Date(anchor.getFullYear(), anchor.getMonth(), 1));
  const last = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
  const days: Date[] = [];
  for (let day = first; day <= last || day.getDay() !== 0; day = addDays(day, 1)) {
    days.push(day);
  }
  return days;
}

/** The time range to ask the API for: from the first day shown to the day after the last. */
export function rangeOf(days: readonly Date[]): { start: Date; end: Date } {
  const first = days[0] ?? startOfDay(new Date());
  const last = days[days.length - 1] ?? first;
  return { start: first, end: addDays(last, 1) };
}

/** The next or previous week or month. */
export function step(span: Span, anchor: Date, by: 1 | -1): Date {
  return span === "week" ? addDays(anchor, 7 * by) : new Date(anchor.getFullYear(), anchor.getMonth() + by, 1);
}

/** "Oct 11 – 17" or "October 2026". */
export function titleOf(span: Span, anchor: Date, locale?: string): string {
  if (span === "month") {
    return anchor.toLocaleDateString(locale, { month: "long", year: "numeric" });
  }
  const [first] = daysShown("week", anchor);
  const last = addDays(first ?? anchor, 6);
  const start = (first ?? anchor).toLocaleDateString(locale, { month: "short", day: "numeric" });
  const end =
    last.getMonth() === (first ?? anchor).getMonth()
      ? String(last.getDate())
      : last.toLocaleDateString(locale, { month: "short", day: "numeric" });
  return `${start} – ${end}`;
}

/** Items by local day, keeping their order. */
export function byDay<T>(items: readonly T[], when: (item: T) => string): Map<string, T[]> {
  const days = new Map<string, T[]>();
  for (const item of items) {
    const key = dayKey(new Date(when(item)));
    days.set(key, [...(days.get(key) ?? []), item]);
  }
  return days;
}
