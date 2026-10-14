"use client";

import Link from "next/link";

import type { Night } from "@/lib/nights";

import { NightCard } from "./night-card";
import { useHomeRefresh } from "./home-refresh";
import { useApiGet } from "./use-api";

/** Home: the next meetup across your groups, to answer in one tap. The rest are on Play. */
export function NextNight() {
  const { result, reload } = useApiGet<Night[]>("/v1/me/nights");
  useHomeRefresh(reload);
  const next = result.kind === "ready" ? result.data[0] : undefined;
  if (!next) {
    return null;
  }
  return (
    <section aria-labelledby="next-night-heading" className="flex animate-rise flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 id="next-night-heading" className="text-title-sm font-bold text-ink">
          Next meetup
        </h2>
        <Link href="/play" className="inline-flex min-h-11 items-center text-small font-bold text-primary">
          All meetups
        </Link>
      </div>
      <NightCard night={next} showGroup onChange={reload} />
    </section>
  );
}
