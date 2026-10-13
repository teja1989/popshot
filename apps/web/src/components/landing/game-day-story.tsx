"use client";

import { AnimatePresence, motion, useMotionValueEvent, useReducedMotion, useScroll } from "motion/react";
import { useRef, useState, type ReactNode } from "react";

import { CourtPhoto } from "./photos";

import { useEntrance } from "./reveal";

// "Every game day becomes a story": three steps, play, log, recap. On wide screens the
// section pins while you scroll and the picture changes with each step; on phones the
// steps simply stack. All example data.

const STEPS = [
  {
    eyebrow: "1 · Play",
    title: "Play like you always do.",
    body: "Popshot stays in your pocket until the game's done. No live scoring, no fuss at the kitchen line.",
  },
  {
    eyebrow: "2 · Log",
    title: "Log it in a few taps.",
    body: "Pick who played and tap in the score. Popshot checks it's a real final score, and your whole crew sees it straight away.",
  },
  {
    eyebrow: "3 · Recap",
    title: "Get the story of the day.",
    body: "After you play, Popshot writes up the outing: the close games, the comebacks and friendly awards for showing up and welcoming new players.",
  },
] as const;

export function GameDayStory() {
  // Reduced motion: no pinning, every step with its own picture, as on phones.
  const pinned = !useReducedMotion();
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });
  const [step, setStep] = useState(0);
  useMotionValueEvent(scrollYProgress, "change", (progress) => {
    setStep(Math.min(STEPS.length - 1, Math.floor(progress * STEPS.length)));
  });

  return (
    <section ref={ref} aria-labelledby="story-heading" className={`relative ${pinned ? "lg:h-[300vh]" : ""}`}>
      <div
        className={`flex flex-col gap-10 ${pinned ? "lg:sticky lg:top-0 lg:grid lg:h-screen lg:grid-cols-2 lg:items-center lg:gap-16" : ""}`}
      >
        <div className="flex flex-col gap-6">
          <p className="text-meta font-bold tracking-[0.14em] text-primary uppercase">Every game day becomes a story</p>
          <h2 id="story-heading" className="text-display-sm font-extrabold tracking-[-0.02em] lg:text-display">
            Play. Log. Relive it.
          </h2>
          <ol className="flex flex-col gap-3">
            {STEPS.map((item, index) => (
              <li
                key={item.title}
                className={`rounded-2xl border p-5 transition-colors duration-300 ${
                  !pinned
                    ? ""
                    : index === step
                      ? "lg:border-primary lg:bg-surface"
                      : "lg:border-transparent lg:opacity-55"
                } border-line bg-surface`}
              >
                <p className="text-meta font-bold tracking-[0.1em] text-muted uppercase">{item.eyebrow}</p>
                <p className="mt-1 text-title-sm font-extrabold">{item.title}</p>
                <p className="mt-1 text-body leading-relaxed text-muted">{item.body}</p>
                {/* Phones: each step shows its own picture. */}
                <div className={`mt-4 ${pinned ? "lg:hidden" : ""}`} aria-hidden="true">
                  <StepVisual index={index} />
                </div>
              </li>
            ))}
          </ol>
        </div>
        <div className={pinned ? "hidden lg:block" : "hidden"} aria-hidden="true">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={step}
              initial={{ opacity: 0, y: 24, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -24, scale: 0.98 }}
              transition={{ duration: 0.35, ease: [0.3, 0.7, 0.2, 1] }}
            >
              <StepVisual index={step} />
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
}

const card = "rounded-3xl border border-line bg-surface p-5 shadow-[0_18px_40px_-28px_rgb(15_27_38/0.35)] sm:p-6";

function StepVisual({ index }: { index: number }) {
  if (index === 0) {
    return (
      <div className="overflow-hidden rounded-3xl shadow-[0_18px_40px_-28px_rgb(15_27_38/0.5)]">
        <CourtPhoto />
      </div>
    );
  }
  if (index === 1) {
    return <LogCard />;
  }
  return <RecapSample />;
}

function LogCard() {
  return (
    <div className={`${card} flex flex-col gap-4`}>
      <p className="text-meta font-bold tracking-[0.1em] text-muted uppercase">Log a game · Doubles to 11</p>
      <div className="grid grid-cols-[1fr_auto] items-center gap-y-2">
        <span className="text-lead font-bold">You &amp; Alex</span>
        <ScoreBox value="11" />
        <span className="text-lead font-bold text-muted">Riley &amp; Sam</span>
        <ScoreBox value="9" />
      </div>
      <p className="flex items-center gap-2 text-small font-bold text-win">
        <span className="flex size-6 items-center justify-center rounded-full bg-win text-micro text-on-win">✓</span>
        You &amp; Alex win 11–9. Looks right.
      </p>
    </div>
  );
}

function ScoreBox({ value }: { value: string }) {
  return (
    <span className="flex h-12 w-16 items-center justify-center rounded-xl border border-line bg-bg text-title-lg font-extrabold font-numeral">
      {value}
    </span>
  );
}

const AWARDS: { title: string; why: string; who: string }[] = [
  { title: "Always There", why: "6 weeks in a row", who: "Jo" },
  { title: "Welcome Wagon", why: "Partnered a first-timer", who: "Sam" },
  { title: "Close Call", why: "Won a game by two", who: "You & Alex" },
];

/** A recap as the app shows it: headline, the commentator's lines, then awards. */
export function RecapSample({ children }: { children?: ReactNode }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="relative isolate overflow-hidden rounded-3xl bg-hero p-6 text-on-hero">
        <p className="text-small font-bold text-on-hero-muted">Tuesday · Riverside Park · 7 games · 6 players</p>
        <p className="mt-2 text-title-lg leading-[1.1] font-extrabold tracking-[-0.01em] font-display">
          Seven games, two comebacks and a very loud Tuesday.
        </p>
        <ul className="mt-3 flex flex-col gap-1.5 text-body leading-snug">
          <li>Jo and Sam came back from 4–9 to take the last game 11–9.</li>
          <li>Pat played a first night with the crew and won twice.</li>
        </ul>
        <p className="mt-3 text-meta font-bold text-on-hero-muted">
          Example · Written by AI (Google Gemini) from the games.
        </p>
      </div>
      <ul className="grid gap-2 sm:grid-cols-3">
        {AWARDS.map((award, i) => (
          <AwardItem key={award.title} award={award} index={i} />
        ))}
      </ul>
      {children}
    </div>
  );
}

function AwardItem({ award, index }: { award: (typeof AWARDS)[number]; index: number }) {
  const entrance = useEntrance({ opacity: 0, y: 16 }, { delay: 0.15 + index * 0.1 });
  return (
    <motion.li className="rounded-2xl border border-line bg-surface p-4" {...entrance}>
      <p className="text-small font-extrabold">{award.title}</p>
      <p className="text-meta text-muted">{award.why}</p>
      <p className="mt-2 text-small font-bold text-primary">{award.who}</p>
    </motion.li>
  );
}
