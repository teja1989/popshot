"use client";

import Link from "next/link";

import { playedWhen } from "@/lib/games";
import { outingSize, type RecapSummary } from "@/lib/recaps";

import { useApiGet } from "./use-api";
import { ChevronIcon } from "./ui/icons";

/** The Crew tab's latest outing, and a few before it. Nothing until the first game. */
export function RecapCard({ groupId }: { groupId: string }) {
  const { result } = useApiGet<RecapSummary[]>(`/v1/groups/${groupId}/recaps`);
  if (result.kind !== "ready" || result.data.length === 0) {
    return null;
  }
  const [latest, ...earlier] = result.data;
  if (!latest) {
    return null;
  }
  const href = (key: string) => `/groups/${groupId}/recaps/${key}`;

  return (
    <section aria-labelledby="recap-heading" className="flex animate-rise flex-col gap-2">
      <h2 id="recap-heading" className="text-title-sm font-bold text-ink">
        Latest outing
      </h2>
      <Link
        href={href(latest.key)}
        className="relative isolate flex flex-col gap-2 overflow-hidden rounded-2xl bg-hero p-5 text-on-hero no-underline"
      >
        <span className="text-small font-bold text-on-hero-muted">
          {playedWhen(latest.start)}
          {latest.venue ? ` · ${latest.venue}` : ""}
        </span>
        <span className="text-title leading-tight font-extrabold font-display">{latest.headline}</span>
        <span className="flex items-center justify-between text-body font-bold">
          <span className="text-on-hero-muted">{outingSize(latest)}</span>
          <span className="flex items-center gap-1 text-ball">
            See the recap
            <ChevronIcon />
          </span>
        </span>
      </Link>
      {earlier.length > 0 && (
        <ul
          aria-label="Earlier outings"
          className="overflow-hidden rounded-3xl border border-transparent bg-surface shadow-card"
        >
          {earlier.slice(0, 3).map((r) => (
            <li key={r.key} className="border-b border-line last:border-b-0">
              <Link
                href={href(r.key)}
                className="flex min-h-12 items-center justify-between gap-3 px-4 py-2 text-body text-ink no-underline"
              >
                <span className="truncate font-bold">{playedWhen(r.start)}</span>
                <span className="shrink-0 text-muted">{outingSize(r)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
