"use client";

import Link from "next/link";

import { COPY, FEATURE, periodLabel, type Checkin } from "@/lib/journey";
import { pickAction } from "@/lib/library";

import { useFeaturesLoaded, useYouFeature } from "./features";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";
import { CourtPattern } from "./ui/court-pattern";
import { BackIcon } from "./ui/icons";

const MAIN = "mx-auto flex w-full max-w-md flex-col gap-5 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10";

/** One journey check-in: two weeks of your pickleball, a win first, then one thing to try. */
export function CheckinView({ checkinId }: { checkinId: string }) {
  const loaded = useFeaturesLoaded();
  const on = useYouFeature(FEATURE);
  return (
    <main className={MAIN}>
      <Link
        href="/you/journey"
        className="-ml-1 flex min-h-11 items-center gap-1.5 self-start text-body font-bold text-primary no-underline"
      >
        <BackIcon />
        Your journey
      </Link>
      {!loaded && <p className="text-muted">Loading…</p>}
      {loaded && !on && <p className="text-body text-muted">{COPY.off}</p>}
      {loaded && on && <CheckinBody checkinId={checkinId} />}
    </main>
  );
}

function CheckinBody({ checkinId }: { checkinId: string }) {
  // Opening it writes its words the first time, so this can take a moment.
  const { result, reload } = useApiGet<Checkin>(`/v1/me/journey/checkins/${checkinId}`);
  if (result.kind === "loading") {
    return <p className="text-muted">{COPY.checkinLoading}</p>;
  }
  if (result.kind === "error") {
    return result.status === 404 ? (
      <h1 className="text-title-lg font-extrabold">{COPY.checkinMissing}</h1>
    ) : (
      <div
        role="alert"
        className="flex flex-col items-start gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-5"
      >
        <p>We couldn&apos;t load this check-in just now.</p>
        <button type="button" className={buttonClass("quiet")} onClick={reload}>
          Try again
        </button>
      </div>
    );
  }
  const checkin = result.data;
  return (
    <>
      <section className="relative isolate flex animate-rise flex-col gap-3 overflow-hidden rounded-[28px] bg-hero p-6 text-on-hero">
        <CourtPattern />
        <p className="text-meta font-bold text-on-hero-muted">
          {periodLabel(checkin.period_start, checkin.period_end)}
          {checkin.chapter && !checkin.new_chapter ? ` · ${checkin.chapter}` : ""}
        </p>
        {checkin.new_chapter && checkin.chapter && (
          <p
            className="self-start rounded-full bg-ball px-3 py-1 text-small font-extrabold text-on-ball"
            data-new-chapter
          >
            {COPY.newChapter}: {checkin.chapter}
          </p>
        )}
        <h1 className="text-title-lg leading-[1.1] font-extrabold tracking-[-0.01em] font-display">
          {checkin.headline}
        </h1>
        <ul className="flex flex-col gap-2 text-lead leading-snug">
          {checkin.lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </section>

      <section
        aria-labelledby="try-next-heading"
        className="flex animate-rise flex-col gap-2 rounded-3xl bg-secondary-container p-5 text-on-secondary-container [animation-delay:90ms]"
      >
        <h2 id="try-next-heading" className="text-title-sm font-bold">
          {COPY.checkinTryNext}
        </h2>
        <p className="text-lead">{checkin.try_next}</p>
      </section>

      {checkin.picks.length > 0 && (
        <section aria-labelledby="picks-heading" className="flex animate-rise flex-col gap-2 [animation-delay:180ms]">
          <h2 id="picks-heading" className="text-title-sm font-bold">
            {COPY.checkinPicks}
          </h2>
          <ul className="flex flex-col gap-2">
            {checkin.picks.map((pick) => (
              <li key={pick.id}>
                <a
                  href={pick.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="pressable flex items-center gap-3 rounded-2xl bg-surface p-4 text-ink no-underline shadow-card"
                >
                  <span className="flex min-w-0 grow flex-col">
                    <span className="text-body font-bold break-words">{pick.title}</span>
                    <span className="text-small text-muted">{pick.source}</span>
                  </span>
                  <span className="shrink-0 rounded-full bg-primary px-3 py-1.5 text-small font-bold text-on-primary">
                    {pickAction(pick)}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
