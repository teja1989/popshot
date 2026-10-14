"use client";

import { MotionConfig, motion, useScroll, useTransform } from "motion/react";
import Link from "next/link";
import { useRef } from "react";

import { useAuth } from "./auth";
import { CountVisit } from "./funnel-tracking";
import { GameDayStory } from "./landing/game-day-story";
import { CrewInsights, YourStats } from "./landing/insights";
import { HeroPhoto, PhotoBand } from "./landing/photos";
import { RallyDemo } from "./landing/rally-demo";
import { Reveal } from "./landing/reveal";
import { LegalLinks } from "./legal-page";
import { Brand } from "./ui/brand";
import { buttonClass } from "./ui/button";
import { CourtPattern } from "./ui/court-pattern";
import { ArrowIcon, LockIcon } from "./ui/icons";

// The landing page people see before signing in. Everything shown is either true of the app
// today or an example clearly marked as one: no fake reviews, user counts or rankings.
// Animations use Motion (motion/react); MotionConfig makes them respect "reduce motion".

function SignInButton({ className = "" }: { className?: string }) {
  const { busy, signIn } = useAuth();
  return (
    <button
      type="button"
      className={buttonClass("action", `h-14 px-7 text-title-sm ${className}`)}
      onClick={() => void signIn()}
      disabled={busy}
    >
      Continue with Google
      <ArrowIcon />
    </button>
  );
}

// Under each sign-in button: signing in is agreeing to the terms.
function AgreeNote() {
  return (
    <p className="text-small text-on-hero-muted">
      By continuing, you agree to the{" "}
      <Link href="/terms" className="font-bold text-on-hero underline underline-offset-2">
        terms
      </Link>{" "}
      and{" "}
      <Link href="/privacy" className="font-bold text-on-hero underline underline-offset-2">
        privacy policy
      </Link>
      .
    </p>
  );
}

const VALUES = [
  {
    title: "No rankings, ever",
    body: "No leaderboards and no ladder to climb. Everyone's listed A to Z, and crew points are there to keep games even.",
    accent: "bg-ball",
  },
  {
    title: "Every level welcome",
    body: "First-timers, weekend regulars, morning players and night owls. Awards celebrate showing up and welcoming new people.",
    accent: "bg-primary",
  },
  {
    title: "Private by default",
    body: "No public profiles, no player search, no location sharing. A group is invisible to anyone who isn't in it.",
    accent: "bg-win",
  },
];

const STEPS = [
  ["Start a group", "Name your crew and pick how you usually play."],
  ["Invite your crew", "Share a link or a code. You approve who joins."],
  ["Play and log", "Log after each game. Stats and the recap follow."],
] as const;

export function SignInScreen({ invited = false }: { invited?: boolean }) {
  const { notice } = useAuth();
  const hero = useRef<HTMLElement>(null);
  // As the hero scrolls away, its words drift up a little slower than the page and fade.
  const { scrollYProgress } = useScroll({ target: hero, offset: ["start start", "end start"] });
  const drift = useTransform(scrollYProgress, [0, 1], [0, 120]);
  const fade = useTransform(scrollYProgress, [0, 0.8], [1, 0]);

  return (
    <MotionConfig reducedMotion="user">
      <CountVisit page={invited ? "invite" : "home"} />
      <div className="bg-bg">
        <section ref={hero} className="relative isolate overflow-hidden bg-hero text-on-hero">
          <HeroPhoto />
          <div className="mx-auto grid max-w-6xl gap-12 px-6 pt-8 pb-16 lg:grid-cols-[1.1fr_1fr] lg:items-center lg:gap-12 lg:px-10 lg:pt-10 lg:pb-24">
            <header className="lg:col-span-2">
              <Brand onHero />
            </header>

            <motion.div className="flex flex-col" style={{ y: drift, opacity: fade }}>
              <motion.p
                className="text-meta font-bold tracking-[0.14em] text-ball uppercase"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
              >
                {invited ? "You've been invited" : "Pickleball with your crew"}
              </motion.p>
              <motion.h1
                className="mt-4 text-jumbo font-extrabold tracking-[-0.035em] sm:text-jumbo-lg lg:text-jumbo-xl"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.08 }}
              >
                The friendly <span className="text-ball">pickleball</span> app.
              </motion.h1>
              <motion.p
                className="mt-5 max-w-xl text-title-sm leading-relaxed text-on-hero-muted"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.16 }}
              >
                {invited
                  ? "Someone wants you in their Popshot group. Sign in to see which one and ask to join."
                  : "No rankings. Just your crew, your games, your stats and the story of every game day."}
              </motion.p>
              <motion.div
                className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center"
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.24 }}
              >
                <SignInButton />
                <span className="flex items-center gap-2 text-small text-on-hero-muted">
                  <LockIcon />
                  Private to your crew
                </span>
              </motion.div>
              <div className="mt-3">
                <AgreeNote />
              </div>
              <p role="status" className="mt-3 min-h-6 text-body font-bold text-ball">
                {notice}
              </p>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 30, rotate: -1.5 }}
              animate={{ opacity: 1, y: 0, rotate: 0 }}
              transition={{ delay: 0.3, duration: 0.7, ease: [0.3, 0.7, 0.2, 1] }}
            >
              <RallyDemo />
            </motion.div>
          </div>
        </section>

        <PhotoBand />

        <div className="mx-auto flex max-w-6xl flex-col gap-20 px-6 py-20 lg:gap-28 lg:px-10 lg:py-28">
          <GameDayStory />

          <section
            aria-labelledby="crew-heading"
            className="grid items-center gap-8 lg:grid-cols-[1fr_1.1fr] lg:gap-16"
          >
            <Reveal>
              <p className="text-meta font-bold tracking-[0.14em] text-primary uppercase">Crew insights</p>
              <h2 id="crew-heading" className="mt-3 text-display-sm font-extrabold tracking-[-0.02em] lg:text-display">
                The things your crew will talk about.
              </h2>
              <p className="mt-4 max-w-lg text-lead leading-relaxed text-muted">
                Who&apos;s played the most, the partnerships that click, who&apos;s new and who&apos;s on a streak.
                Worked out from your crew&apos;s games, never a ranking.
              </p>
            </Reveal>
            <CrewInsights />
          </section>

          <section
            aria-labelledby="stats-heading"
            className="grid items-center gap-8 lg:grid-cols-[1.1fr_1fr] lg:gap-16"
          >
            <div className="lg:order-2">
              <Reveal>
                <p className="text-meta font-bold tracking-[0.14em] text-primary uppercase">Your stats</p>
                <h2
                  id="stats-heading"
                  className="mt-3 text-display-sm font-extrabold tracking-[-0.02em] lg:text-display"
                >
                  See yourself getting better.
                </h2>
                <p className="mt-4 max-w-lg text-lead leading-relaxed text-muted">
                  Your form, close games, favourite partners and toughest match-ups, updated every time a game is
                  logged. Only your crew sees them.
                </p>
              </Reveal>
            </div>
            <Reveal className="lg:order-1">
              <YourStats />
            </Reveal>
          </section>

          <section aria-labelledby="values-heading" className="flex flex-col gap-8">
            <Reveal>
              <h2 id="values-heading" className="text-display-sm font-extrabold tracking-[-0.02em] lg:text-display">
                Built for the people you play with.
              </h2>
            </Reveal>
            <ul className="grid gap-4 md:grid-cols-3">
              {VALUES.map((item, i) => (
                <li key={item.title}>
                  <Reveal
                    delay={i * 0.08}
                    className="flex h-full flex-col gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-6"
                  >
                    <span aria-hidden="true" className={`h-1.5 w-12 rounded-full ${item.accent}`} />
                    <p className="text-title-sm font-extrabold">{item.title}</p>
                    <p className="text-body leading-relaxed text-muted">{item.body}</p>
                  </Reveal>
                </li>
              ))}
            </ul>
          </section>

          <section aria-labelledby="how-heading" className="flex flex-col gap-8">
            <Reveal>
              <h2 id="how-heading" className="text-display-sm font-extrabold tracking-[-0.02em] lg:text-display">
                Up and running in three steps.
              </h2>
            </Reveal>
            <ol className="grid gap-4 md:grid-cols-3">
              {STEPS.map(([title, body], i) => (
                <li key={title}>
                  <Reveal
                    delay={i * 0.08}
                    className="flex h-full flex-col gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-6"
                  >
                    <span className="flex size-10 items-center justify-center rounded-full bg-ball text-title-sm font-extrabold text-on-ball font-numeral">
                      {i + 1}
                    </span>
                    <p className="text-title-sm font-extrabold">{title}</p>
                    <p className="text-body text-muted">{body}</p>
                  </Reveal>
                </li>
              ))}
            </ol>
          </section>

          <Reveal>
            <section className="relative isolate flex flex-col items-start gap-6 overflow-hidden rounded-[32px] bg-hero p-8 text-on-hero lg:flex-row lg:items-center lg:justify-between lg:p-14">
              <CourtPattern />
              <h2 className="text-display-sm leading-[1.05] font-extrabold tracking-[-0.02em] lg:text-display">
                Your next game deserves <span className="text-ball">a story.</span>
              </h2>
              <div className="flex flex-col items-start gap-3">
                <SignInButton />
                <AgreeNote />
              </div>
            </section>
          </Reveal>
        </div>

        <footer className="mx-auto flex max-w-6xl flex-col gap-2 px-6 pb-12 text-small text-muted sm:flex-row sm:items-center sm:justify-between lg:px-10">
          <Brand />
          <p>Pickleball stats for the people you actually play with. Screens show example data.</p>
          <LegalLinks />
        </footer>
      </div>
    </MotionConfig>
  );
}
