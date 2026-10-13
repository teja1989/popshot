"use client";

import Link from "next/link";

import { formatInfo, type EventSummary } from "@/lib/events";
import type { GroupSummary } from "@/lib/groups";

import { useFeature } from "./features";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";
import { PlusIcon } from "./ui/icons";

const FINISHED_SHOWN = 3;

/**
 * Play: the crew's events (Dink Shuffle, Ride the River). Shown when an event format is
 * switched on for the crew, or when it has events already (they stay reachable if the
 * switch goes off). Leads and co-leads can start one while a format is on.
 */
export function EventsSection({ group }: { group: GroupSummary }) {
  const anyOn = useFeature("events.*", group.id);
  const { result } = useApiGet<EventSummary[]>(`/v1/groups/${group.id}/events`);
  const events = result.kind === "ready" ? result.data : [];
  const live = events.filter((e) => e.status === "live");
  const finished = events.filter((e) => e.status === "finished").slice(0, FINISHED_SHOWN);
  const canStart = anyOn && (group.my_role === "lead" || group.my_role === "co_lead");

  if (!anyOn && events.length === 0) {
    return null;
  }
  return (
    <section aria-labelledby="events-heading" className="flex animate-rise flex-col gap-2 [animation-delay:45ms]">
      <div className="flex min-h-11 items-center justify-between">
        <h2 id="events-heading" className="text-label font-bold tracking-[0.1em] text-muted uppercase">
          Events
        </h2>
        {canStart && (
          <Link
            href={`/groups/${group.id}/events/new`}
            className={buttonClass("quiet", "min-h-11 gap-1.5 px-3 text-body")}
          >
            <PlusIcon />
            Start one
          </Link>
        )}
      </div>
      {result.kind === "ready" && events.length === 0 && (
        <p className="rounded-2xl border border-dashed border-line p-4 text-body text-muted">
          {canStart
            ? "Run a round robin or ride the river at your next meetup. Popshot makes the rounds; scores become games."
            : "When a lead starts an event, it shows up here."}
        </p>
      )}
      {[...live, ...finished].map((e) => (
        <Link
          key={e.id}
          href={`/groups/${group.id}/events/${e.id}`}
          className="flex items-center justify-between gap-3 rounded-2xl border border-line bg-surface p-4 text-ink no-underline transition-colors duration-150 hover:border-primary"
        >
          <span className="flex min-w-0 flex-col gap-0.5">
            <span className="truncate text-title-sm font-extrabold font-display">{e.name}</span>
            <span className="text-small text-muted">
              {formatInfo(e.kind).name} · {e.players} players ·{" "}
              {e.rounds === 1 ? "round 1" : `${String(e.rounds)} rounds`}
            </span>
          </span>
          <span
            className={`shrink-0 rounded-full px-2.5 py-0.5 text-meta font-bold ${
              e.status === "live" ? "bg-win text-on-win" : "bg-chip text-muted"
            }`}
          >
            {e.status === "live" ? "On now" : "Finished"}
          </span>
        </Link>
      ))}
    </section>
  );
}
