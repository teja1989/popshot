"use client";

import { useState } from "react";

import { CREW_POINTS, DEFAULT_START, LEVELS, points } from "@/lib/board";

import { InfoIcon } from "./ui/icons";
import { Sheet } from "./ui/sheet";

/** An ⓘ button that explains crew points, and how they differ from your self-rated level. */
export function CrewPointsInfo({ tone = "default" }: { tone?: "default" | "hero" }) {
  const [open, setOpen] = useState(false);
  const ex = CREW_POINTS.example;
  const [won, lost] = ex.score;
  return (
    <Sheet
      trigger={
        <button
          type="button"
          aria-label="How crew points work"
          className={`inline-flex size-8 shrink-0 cursor-pointer items-center justify-center rounded-full align-middle ${
            tone === "hero" ? "text-on-hero-muted hover:text-on-hero" : "text-muted hover:text-ink"
          }`}
        >
          <InfoIcon />
        </button>
      }
      open={open}
      onOpenChange={setOpen}
      title="How crew points work"
      description={`A rating from ${points(CREW_POINTS.min)} to ${points(CREW_POINTS.max)} for how you play in this crew.`}
      fullOnPhone
    >
      <div className="flex flex-col gap-5 text-[16px] leading-relaxed">
        <section className="flex flex-col gap-2">
          <h3 className="text-[17px] font-extrabold">After every game</h3>
          <ol className="flex list-decimal flex-col gap-1.5 pl-5">
            <li>
              Before it&apos;s scored, we work out what share of the points each side should win. A side&apos;s
              strength is its players&apos; crew points, averaged.
            </li>
            <li>Then we compare that with the share they actually won.</li>
            <li>Better than expected, your points go up. Worse, they go down. Partners move together.</li>
            <li>
              New players move fast so they find their level; after about {CREW_POINTS.steadyAfter} games the
              moves get smaller.
            </li>
          </ol>
        </section>

        <section className="flex flex-col gap-2 rounded-2xl bg-chip p-4">
          <h3 className="text-[15px] font-extrabold">An example</h3>
          <p>
            You and your partner ({points(ex.team)} each) beat a team on {points(ex.opponents)} {won}–{lost}. You were
            expected to win about {Math.round(ex.expectedShare * 100)}% of the points and won{" "}
            {Math.round((100 * won) / (won + lost))}%, so you both go up: about +{points(ex.changeSettled)} if
            you&apos;ve played a while, +{points(ex.changeNew)} if you&apos;re new. A close win over a weaker team can
            even cost a little.
          </p>
        </section>

        <section className="flex flex-col gap-2">
          <h3 className="text-[17px] font-extrabold">Your level vs. your crew points</h3>
          <p>
            The level you pick on the You page is only where your crew points <strong>start</strong>. Within about{" "}
            {CREW_POINTS.rankedAfter} games your results take over, and changing it later doesn&apos;t move your
            points.
          </p>
          <ul className="grid grid-cols-2 gap-x-4 gap-y-1 text-[15px] text-muted">
            <li>Not set · {points(DEFAULT_START)}</li>
            {LEVELS.map((level) => (
              <li key={level.value}>
                {level.label} · {points(level.start)}
              </li>
            ))}
          </ul>
        </section>

        <section className="flex flex-col gap-2">
          <h3 className="text-[17px] font-extrabold">On the Board</h3>
          <ul className="flex flex-col gap-1.5">
            <li>
              <strong>Ranked</strong>: {CREW_POINTS.rankedAfter} or more games.
            </li>
            <li>
              <strong>Getting started</strong>: fewer than {CREW_POINTS.rankedAfter} games. Your points already count.
            </li>
            <li>
              <strong>Resting</strong>: no games in {CREW_POINTS.restingAfterDays} days. Your points are kept, and one
              game brings you back.
            </li>
          </ul>
          <p className="text-[15px] text-muted">
            Crew points compare you with this crew only, not with other groups or official ratings.
          </p>
        </section>
      </div>
    </Sheet>
  );
}
