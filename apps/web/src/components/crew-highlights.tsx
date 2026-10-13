"use client";

import { hasHighlights, names, type Highlights } from "@/lib/stats";

import { useApiGet } from "./use-api";

/** What's worth celebrating in the crew lately. Says nothing until there's something to say. */
export function CrewHighlights({ groupId }: { groupId: string }) {
  const { result } = useApiGet<Highlights>(`/v1/groups/${groupId}/highlights`);
  if (result.kind !== "ready" || !hasHighlights(result.data)) {
    return null;
  }
  const h = result.data;
  const days = String(h.window_days);
  const weekly = h.weeks_running[0];

  return (
    <section aria-labelledby="highlights-heading" className="flex animate-rise flex-col gap-2">
      <h2 id="highlights-heading" className="text-label font-bold tracking-[0.1em] text-muted uppercase">
        Lately · {days} days
      </h2>
      <ul className="grid gap-2 sm:grid-cols-2">
        {h.most_games && (
          <Card
            label="Most games"
            value={`${String(h.most_games.matches)} games`}
            who={h.most_games.player.display_name}
          />
        )}
        {weekly && (
          <Card
            label="Here every week"
            value={`${String(weekly.weeks)} weeks`}
            who={names(h.weeks_running.filter((w) => w.weeks === weekly.weeks).map((w) => w.player))}
          />
        )}
        {h.best_partnership && (
          <Card
            label="Best partnership"
            value={`${String(h.best_partnership.won)} of ${String(h.best_partnership.played)}`}
            hint="won together"
            who={names(h.best_partnership.players)}
          />
        )}
        {h.newcomers.length > 0 && (
          <Card label="Welcome to the crew" value={`${String(h.newcomers.length)} new`} who={names(h.newcomers)} />
        )}
        {h.longest_win_streak && (
          <Card
            label="Longest win streak"
            value={`${String(h.longest_win_streak.length)} wins`}
            who={h.longest_win_streak.player.display_name}
          />
        )}
      </ul>
    </section>
  );
}

function Card({ label, value, who, hint }: { label: string; value: string; who: string; hint?: string }) {
  // A compact row on phones (what and who on the left, the number on the right); a card from sm up.
  return (
    <li className="flex items-center justify-between gap-3 rounded-2xl border border-line bg-surface px-4 py-3 sm:flex-col sm:items-start sm:justify-start sm:gap-1">
      <span className="flex min-w-0 flex-col sm:contents">
        <span className="text-meta font-bold text-muted sm:order-1">{label}</span>
        <span className="truncate text-body font-bold sm:order-3 sm:max-w-full">{who}</span>
      </span>
      <span className="shrink-0 text-right text-title leading-none font-extrabold tabular-nums font-numeral sm:order-2 sm:text-left">
        {value}
        {hint && <span className="block text-meta font-bold text-muted font-sans sm:inline"> {hint}</span>}
      </span>
    </li>
  );
}
