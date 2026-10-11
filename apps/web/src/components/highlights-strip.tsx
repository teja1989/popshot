"use client";

import { points } from "@/lib/board";
import { hasHighlights, upsetLine, type Highlights } from "@/lib/stats";

import { useApiGet } from "./use-api";

/** The crew's highlights at the top of the Board. Says nothing until there's something to say. */
export function HighlightsStrip({ groupId }: { groupId: string }) {
  const { result } = useApiGet<Highlights>(`/v1/groups/${groupId}/highlights`);
  if (result.kind !== "ready" || !hasHighlights(result.data)) {
    return null;
  }
  const h = result.data;
  const days = String(h.window_days);

  return (
    <section aria-labelledby="highlights-heading" className="flex animate-rise flex-col gap-2">
      <h2 id="highlights-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
        Highlights
      </h2>
      <ul className="grid gap-2 sm:grid-cols-3">
        {h.longest_win_streak && (
          <Card label="Longest win streak" value={`${String(h.longest_win_streak.length)} wins`} who={h.longest_win_streak.player.display_name} />
        )}
        {h.most_games && (
          <Card
            label={`Most games · ${days} days`}
            value={`${String(h.most_games.matches)} games`}
            who={h.most_games.player.display_name}
          />
        )}
        {h.biggest_upset && (
          <Card
            label={`Biggest upset · ${days} days`}
            value={points(h.biggest_upset.gap)}
            who={upsetLine(h.biggest_upset)}
            hint="points behind"
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
        <span className="text-[13px] font-bold text-muted sm:order-1">{label}</span>
        <span className="truncate text-[15px] font-bold sm:order-3 sm:max-w-full">{who}</span>
      </span>
      <span className="shrink-0 text-right text-[24px] leading-none font-extrabold tabular-nums [font-stretch:75%] sm:order-2 sm:text-left">
        {value}
        {hint && <span className="block text-[13px] font-bold text-muted [font-stretch:100%] sm:inline"> {hint}</span>}
      </span>
    </li>
  );
}
