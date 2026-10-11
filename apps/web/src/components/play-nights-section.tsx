"use client";

import type { Night } from "@/lib/nights";

import { NightCard } from "./night-card";
import { PlanNightSheet } from "./plan-night-sheet";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";
import { PlusIcon } from "./ui/icons";

const SHOWN = 4;

/** The group's upcoming play nights, and a button to plan one. */
export function PlayNightsSection({ groupId }: { groupId: string }) {
  const { result, reload } = useApiGet<Night[]>(`/v1/groups/${groupId}/nights`);
  const nights = result.kind === "ready" ? result.data : [];
  const lastVenue = nights.at(-1)?.venue;

  return (
    <section aria-labelledby="nights-heading" className="flex animate-rise flex-col gap-2 [animation-delay:30ms]">
      <div className="flex min-h-11 items-center justify-between">
        <h2 id="nights-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
          Play nights
        </h2>
        <PlanNightSheet
          groupId={groupId}
          lastVenue={lastVenue}
          onSaved={reload}
          trigger={
            <button type="button" className={buttonClass("quiet", "min-h-11 gap-1.5 px-3 text-[15px]")}>
              <PlusIcon />
              Plan one
            </button>
          }
        />
      </div>
      {result.kind === "ready" && nights.length === 0 && (
        <p className="rounded-2xl border border-dashed border-line p-4 text-[15px] text-muted">
          Nothing planned yet. Plan the next one and your crew can say if they&apos;re in.
        </p>
      )}
      {nights.slice(0, SHOWN).map((night) => (
        <NightCard key={night.id} night={night} onChange={reload} />
      ))}
      {nights.length > SHOWN && (
        <p className="text-[14px] text-muted">
          And {nights.length - SHOWN} more planned. They show up here as the dates get closer.
        </p>
      )}
    </section>
  );
}
