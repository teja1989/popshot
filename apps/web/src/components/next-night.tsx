"use client";

import type { Night } from "@/lib/nights";

import { NightCard } from "./night-card";
import { useHomeRefresh } from "./home-refresh";
import { useApiGet } from "./use-api";

/** Home: the next play night across your groups, to answer in one tap. */
export function NextNight() {
  const { result, reload } = useApiGet<Night[]>("/v1/me/nights");
  useHomeRefresh(reload);
  const next = result.kind === "ready" ? result.data[0] : undefined;
  if (!next) {
    return null;
  }
  return (
    <section aria-labelledby="next-night-heading" className="flex animate-rise flex-col gap-2">
      <h2 id="next-night-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
        Next meetup
      </h2>
      <NightCard night={next} showGroup onChange={reload} />
    </section>
  );
}
