// Your week on Home. The shape matches the API's routes/week.py (GET /v1/me/week).

export interface YourWeek {
  since: string;
  until: string;
  games: number;
  wins: number;
  close_games: number;
  longest_win_streak: number;
  crews: string[];
  top_partner: { name: string; games: number } | null;
  headline: string;
  lines: string[];
}

/** The days the week covers, in your local time: "Oct 6 – 13", or "Sep 29 – Oct 6". */
export function weekRange(week: Pick<YourWeek, "since" | "until">, locale?: string): string {
  const format = new Intl.DateTimeFormat(locale, { month: "short", day: "numeric" });
  return format.formatRange(new Date(week.since), new Date(week.until));
}
