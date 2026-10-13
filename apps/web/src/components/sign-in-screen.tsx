"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import { useAuth } from "./auth";
import { LegalLinks } from "./legal-page";
import { PhonePreview } from "./phone-preview";
import { Brand } from "./ui/brand";
import { buttonClass } from "./ui/button";
import { CourtArt } from "./ui/court-art";
import { CourtPattern } from "./ui/court-pattern";
import { ArrowIcon, LockIcon } from "./ui/icons";

// The landing page people see before signing in. Everything shown is either true of the app
// today or an example clearly marked as one: no fake reviews, user counts or rankings.

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

const HIGHLIGHTS = ["Meet new players", "Stay active", "Play your way"];

const TOGETHER = [
  {
    title: "Meet your people",
    body: "Open play turns strangers into a regular crew. Popshot gives that crew a home.",
    accent: "bg-ball",
  },
  {
    title: "Move more, smile more",
    body: "Quick games, plenty of laughs, and a reason to be back on court next week.",
    accent: "bg-primary",
  },
  {
    title: "Friendly, whatever your level",
    body: "Keep score, celebrate the good shots, and still tap paddles at the net.",
    accent: "bg-win",
  },
];

export function SignInScreen({ invited = false }: { invited?: boolean }) {
  const { notice } = useAuth();
  return (
    <div className="bg-bg">
      <section className="relative isolate overflow-hidden bg-hero text-on-hero">
        <CourtPattern />
        <div className="mx-auto grid max-w-6xl gap-12 px-6 pt-8 pb-16 lg:grid-cols-[1.15fr_1fr] lg:items-center lg:gap-10 lg:px-10 lg:pt-10 lg:pb-24">
          <header className="lg:col-span-2">
            <Brand onHero />
          </header>

          <div className="flex flex-col">
            <p className="animate-rise text-meta font-bold tracking-[0.14em] text-ball uppercase">
              {invited ? "You've been invited" : "Pickleball with your crew"}
            </p>
            <h1 className="mt-4 animate-rise text-jumbo leading-[0.95] font-[820] tracking-[-0.035em] [animation-delay:80ms] font-display sm:text-jumbo-lg lg:text-jumbo-xl">
              More rallies, more <span className="text-ball">friends.</span>
            </h1>
            <p className="mt-6 max-w-xl animate-rise text-title-sm leading-relaxed text-on-hero-muted [animation-delay:160ms] lg:text-title-sm">
              {invited
                ? "Someone wants you in their Popshot group. Sign in to see which one and ask to join."
                : "Play, laugh and stay active. Popshot keeps the score so you can enjoy the game, and your crew gets the streaks and the stories."}
            </p>
            <div className="mt-8 flex animate-rise flex-col gap-4 [animation-delay:240ms] sm:flex-row sm:items-center">
              <SignInButton />
              <span className="flex items-center gap-2 text-small text-on-hero-muted">
                <LockIcon />
                Private to your crew
              </span>
            </div>
            <div className="mt-3">
              <AgreeNote />
            </div>
            <p role="status" className="mt-3 min-h-6 text-body font-bold text-ball">
              {notice}
            </p>
            <ul className="mt-4 flex flex-wrap gap-2" aria-label="Highlights">
              {HIGHLIGHTS.map((item) => (
                <li
                  key={item}
                  className="rounded-full border border-hero-line px-3.5 py-1.5 text-meta font-bold text-on-hero"
                >
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <PhonePreview />
        </div>
      </section>

      <div className="mx-auto flex max-w-6xl flex-col gap-20 px-6 py-20 lg:gap-28 lg:px-10 lg:py-28">
        <section aria-labelledby="together-heading" className="flex flex-col gap-8">
          <h2 id="together-heading" className="text-display-sm leading-tight font-extrabold tracking-[-0.02em] font-display lg:text-display">
            Pickleball is better together.
          </h2>
          <ul className="grid gap-4 md:grid-cols-3">
            {TOGETHER.map((item) => (
              <li key={item.title} className="flex flex-col gap-3 overflow-hidden rounded-3xl border border-line bg-surface p-6">
                <span aria-hidden="true" className={`h-1.5 w-12 rounded-full ${item.accent}`} />
                <p className="text-title-sm font-extrabold">{item.title}</p>
                <p className="text-lead leading-relaxed text-muted">{item.body}</p>
              </li>
            ))}
          </ul>
        </section>

        <Feature
          eyebrow="Fast at the fence"
          title="Logged before the next game starts."
          body="Pick who played, tap in the score, done. Popshot checks it's a real final score (games to 11, 15 or 21, win by 2) so typos don't sneak in."
          visual={<LogVisual />}
        />
        <Feature
          flip
          eyebrow="Fair records"
          title="Every game, on the record."
          body="Log it once and it counts. Your whole crew sees every game, so there's no more “pretty sure we won that one.” Whoever logged a score can fix a typo."
          visual={<RecordVisual />}
        />
        <Feature
          eyebrow="Partners & match-ups"
          title="Know your best partners."
          body="See which partner makes you better, who you click with, and your toughest match-ups. Records, close games and streaks, all from your crew's games."
          visual={<RivalsVisual />}
        />
        <Feature
          flip
          eyebrow="Your crew"
          title="Celebrate the people you play with."
          body="Who's been here every week, the partnerships that click, and who's new to the crew. No rankings: everyone's listed A to Z, and your crew points are there to keep games even."
          visual={<CrewVisual />}
        />

        <section aria-labelledby="how-heading" className="flex flex-col gap-8">
          <h2 id="how-heading" className="text-display-sm leading-tight font-extrabold tracking-[-0.02em] font-display lg:text-display">
            Up and running in three steps.
          </h2>
          <ol className="grid gap-4 md:grid-cols-3">
            {[
              ["Start a group", "Name your crew and pick how you usually play."],
              ["Invite your crew", "Share an invite link. You approve who joins."],
              ["Play and log", "Log after each game. It counts straight away."],
            ].map(([title, body], i) => (
              <li key={title} className="flex flex-col gap-3 rounded-3xl border border-line bg-surface p-6">
                <span className="flex size-11 items-center justify-center rounded-full bg-ball text-title-sm font-extrabold text-on-ball font-numeral">
                  {i + 1}
                </span>
                <p className="text-title-sm font-extrabold">{title}</p>
                <p className="text-lead text-muted">{body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="flex flex-col gap-4 rounded-3xl border border-line bg-surface p-7 sm:flex-row sm:items-center sm:gap-6 lg:p-9">
          <span className="flex size-14 shrink-0 items-center justify-center rounded-2xl bg-chip text-primary">
            <LockIcon />
          </span>
          <div>
            <h2 className="text-title font-extrabold">Private by default.</h2>
            <p className="mt-1 text-lead text-muted">
              No public profiles, no player search, no location sharing. A group is invisible to
              anyone who isn&apos;t in it.
            </p>
          </div>
        </section>

        <section className="relative isolate flex flex-col items-start gap-6 overflow-hidden rounded-[32px] bg-hero p-8 text-on-hero lg:flex-row lg:items-center lg:justify-between lg:p-14">
          <CourtPattern />
          <h2 className="text-display-sm leading-[1.05] font-extrabold tracking-[-0.02em] font-display lg:text-display">
            Tally every <span className="text-ball">rally.</span>
          </h2>
          <div className="flex flex-col items-start gap-3">
            <SignInButton />
            <AgreeNote />
          </div>
        </section>
      </div>

      <footer className="mx-auto flex max-w-6xl flex-col gap-2 px-6 pb-12 text-small text-muted sm:flex-row sm:items-center sm:justify-between lg:px-10">
        <Brand />
        <p>Pickleball stats for the people you actually play with. Screens show example data.</p>
        <LegalLinks />
      </footer>
    </div>
  );
}

function Feature({
  eyebrow,
  title,
  body,
  visual,
  flip = false,
}: {
  eyebrow: string;
  title: string;
  body: string;
  visual: ReactNode;
  flip?: boolean;
}) {
  return (
    <section className="grid items-center gap-8 lg:grid-cols-2 lg:gap-16">
      <div className={flip ? "lg:order-2" : ""}>
        <p className="text-meta font-bold tracking-[0.14em] text-primary uppercase">{eyebrow}</p>
        <h2 className="mt-3 text-display-sm leading-[1.05] font-extrabold tracking-[-0.02em] font-display lg:text-display">
          {title}
        </h2>
        <p className="mt-4 max-w-lg text-title-sm leading-relaxed text-muted">{body}</p>
      </div>
      <div className={flip ? "lg:order-1" : ""} aria-hidden="true">
        {visual}
      </div>
    </section>
  );
}

const card = "rounded-3xl border border-line bg-surface p-6 shadow-[0_18px_40px_-28px_rgb(15_27_38/0.35)]";

function LogVisual() {
  return (
    <div className={`${card} flex flex-col gap-4`}>
      <CourtArt rally className="w-full" />
      <div className="flex items-center justify-between">
        <span className="text-body font-bold">You &amp; Alex</span>
        <span className="text-display leading-none font-extrabold font-numeral">11 – 9</span>
        <span className="text-body font-bold text-muted">Riley &amp; Sam</span>
      </div>
      <p className="text-small font-bold text-win">✓ You &amp; Alex win 11–9. Looks right.</p>
    </div>
  );
}

function RecordVisual() {
  return (
    <div className={`${card} flex flex-col gap-4`}>
      <p className="text-meta font-bold tracking-[0.1em] text-muted uppercase">Logged by Sam · just now</p>
      <div className="flex items-center justify-between">
        <span className="text-lead font-bold">Casey &amp; Sam</span>
        <span className="text-display leading-none font-extrabold font-numeral">11 – 8</span>
        <span className="text-lead font-bold">You &amp; Alex</span>
      </div>
      <div className="flex items-center gap-3 rounded-2xl bg-chip p-3">
        <span className="flex size-10 items-center justify-center rounded-full bg-win text-title-sm font-extrabold text-on-win">✓</span>
        <span className="text-body font-bold">On the record for the whole crew.</span>
      </div>
    </div>
  );
}

function RivalsVisual() {
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className={card}>
        <p className="text-meta font-bold tracking-[0.1em] text-muted uppercase">Toughest match-up</p>
        <p className="mt-2 text-display-sm font-extrabold font-display">Riley</p>
        <p className="text-body text-muted">2–5 head to head</p>
        <div className="mt-4 flex h-2.5 overflow-hidden rounded-full bg-chip">
          <span className="w-[29%] origin-left animate-grow-x bg-win" />
        </div>
      </div>
      <div className={card}>
        <p className="text-meta font-bold tracking-[0.1em] text-muted uppercase">Best partner</p>
        <p className="mt-2 text-display-sm font-extrabold font-display">Alex</p>
        <p className="text-body text-muted">9–2 together</p>
        <div className="mt-4 flex h-2.5 overflow-hidden rounded-full bg-chip">
          <span className="w-[82%] origin-left animate-grow-x bg-win" />
        </div>
      </div>
    </div>
  );
}

function CrewVisual() {
  const rows = [
    ["Here every week", "Jo and Sam", "5 weeks"],
    ["Best partnership", "Alex and Riley", "6 of 7"],
    ["Welcome to the crew", "Pat", "1 new"],
  ] as const;
  return (
    <ul className={`${card} flex flex-col gap-3`}>
      {rows.map(([label, who, value]) => (
        <li key={label} className="flex items-center justify-between gap-3 border-b border-line pb-3 last:border-b-0 last:pb-0">
          <span className="flex min-w-0 flex-col">
            <span className="text-meta font-bold text-muted">{label}</span>
            <span className="truncate text-lead font-bold">{who}</span>
          </span>
          <span className="shrink-0 text-title font-extrabold font-numeral">{value}</span>
        </li>
      ))}
    </ul>
  );
}
