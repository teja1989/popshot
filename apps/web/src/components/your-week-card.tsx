"use client";

import { weekRange, type YourWeek } from "@/lib/week";

import { useHomeRefresh } from "./home-refresh";
import { useApiGet } from "./use-api";

/**
 * Home: a short look back at your own last 7 days. It's yours only and never compares you
 * with anyone. It stays out of the way while loading, or if it can't load: it's a nice extra.
 */
export function YourWeekCard() {
  const { result, reload } = useApiGet<YourWeek>("/v1/me/week");
  useHomeRefresh(reload);
  if (result.kind !== "ready") {
    return null;
  }
  const week = result.data;
  return (
    <section
      aria-labelledby="your-week-heading"
      className="flex animate-rise flex-col gap-3 rounded-3xl border border-line bg-surface p-5"
    >
      <div className="flex items-baseline justify-between gap-3">
        <h2 id="your-week-heading" className="text-label font-bold tracking-[0.1em] text-muted uppercase">
          Your week
        </h2>
        <p className="text-meta text-muted">{weekRange(week)}</p>
      </div>
      <p className="text-title-sm font-extrabold font-display">{week.headline}</p>
      {week.games > 0 && (
        <dl className="grid grid-cols-3 gap-3">
          <WeekStat label="Games" value={week.games} />
          <WeekStat label="Wins" value={week.wins} />
          <WeekStat label="Close games" value={week.close_games} />
        </dl>
      )}
      <ul className="flex flex-col gap-1.5 text-body leading-relaxed">
        {week.lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </section>
  );
}

function WeekStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-meta text-muted">{label}</dt>
      <dd className="text-title-lg leading-none font-extrabold tabular-nums font-numeral">{value}</dd>
    </div>
  );
}
