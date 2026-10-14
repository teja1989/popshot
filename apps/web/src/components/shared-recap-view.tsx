import Link from "next/link";

import { describeAward, outingSize } from "@/lib/recaps";
import { gamesText, namesText, teamAWon, type SharedRecap } from "@/lib/shares";

import { CountVisit, TryPopshotLink } from "./funnel-tracking";
import { LocalDate } from "./local-date";
import { Avatar } from "./ui/avatar";
import { Brand } from "./ui/brand";
import { buttonClass } from "./ui/button";
import { CourtPattern } from "./ui/court-pattern";

/** A recap someone shared: the story, awards, who played and the scores. No sign-in needed. */
export function SharedRecapView({ recap }: { recap: SharedRecap }) {
  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-5 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <CountVisit page="recap" />
      <Link
        href="/"
        aria-label="Popshot home"
        className="inline-flex min-h-11 items-center self-start text-ink no-underline"
      >
        <Brand />
      </Link>

      <section className="relative isolate flex animate-rise flex-col gap-3 overflow-hidden rounded-[28px] bg-hero p-6 text-on-hero">
        <CourtPattern />
        <p className="text-small font-bold text-on-hero-muted">
          {recap.crew} · {outingSize(recap)}
        </p>
        <h1 className="text-title-lg leading-[1.1] font-extrabold tracking-[-0.01em] font-display">{recap.headline}</h1>
        <ul className="flex flex-col gap-2 text-lead leading-snug">
          {recap.lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        <p className="text-meta font-bold text-on-hero-muted">
          <LocalDate iso={recap.start} />
          {recap.written_by === "ai" ? " · Written by AI (Google Gemini) from the games." : ""}
        </p>
      </section>

      {recap.awards.length > 0 && (
        <section aria-labelledby="awards-heading" className="flex flex-col gap-2">
          <h2 id="awards-heading" className="text-title-sm font-bold text-ink">
            Awards
          </h2>
          <ul className="grid gap-2 sm:grid-cols-2">
            {recap.awards.map((award) => {
              const { title, why } = describeAward(award);
              return (
                <li
                  key={`${award.kind}-${award.names.join()}-${String(award.more)}`}
                  className="flex flex-col gap-1 rounded-3xl border border-transparent bg-surface shadow-card p-4"
                >
                  <span className="flex items-center gap-2 text-lead font-extrabold">
                    <span aria-hidden="true" className="size-2.5 rounded-full bg-ball" />
                    {title}
                  </span>
                  <span className="text-lead font-bold">{namesText(award)}</span>
                  <span className="text-small text-muted">{why}</span>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <section aria-labelledby="played-heading" className="flex flex-col gap-2">
        <h2 id="played-heading" className="text-title-sm font-bold text-ink">
          Who played
        </h2>
        <ul className="flex flex-wrap gap-2">
          {recap.played.map(({ name, games }, i) => (
            <li
              // Names can repeat ("Crew member"), so the position keeps keys unique.
              key={`${name}-${String(i)}`}
              className="flex items-center gap-2 rounded-full border border-line bg-surface py-1 pr-3 pl-1"
            >
              <Avatar name={name} size="sm" />
              <span className="text-body font-bold">{name}</span>
              <span className="text-small text-muted">{games}</span>
            </li>
          ))}
        </ul>
      </section>

      <section aria-labelledby="games-heading" className="flex flex-col gap-2">
        <h2 id="games-heading" className="text-title-sm font-bold text-ink">
          The games
        </h2>
        <ol className="overflow-hidden rounded-3xl border border-transparent bg-surface shadow-card">
          {recap.matches.map((m, i) => {
            const aWon = teamAWon(m.games);
            const [winners, others] = aWon ? [m.team_a, m.team_b] : [m.team_b, m.team_a];
            const scores = aWon ? m.games : m.games.map(([a, b]): [number, number] => [b, a]);
            return (
              <li key={String(i)} className="flex flex-col gap-0.5 border-b border-line px-4 py-3 last:border-b-0">
                <span className="text-lead font-bold">{winners.join(" & ")}</span>
                <span className="text-body text-muted">
                  {gamesText(scores)} · vs {others.join(" & ")}
                </span>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="mt-2 flex flex-col items-start gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-5">
        <p className="text-lead font-extrabold">Keep score with your own crew.</p>
        <p className="text-body text-muted">
          Popshot logs your games, plans meetups and writes a recap like this after you play.
        </p>
        <TryPopshotLink className={buttonClass("primary")}>Try Popshot</TryPopshotLink>
      </section>
      <p className="text-meta text-muted">
        Shared by someone in {recap.crew}. First names only. This link stops working on{" "}
        <LocalDate iso={recap.expires_at} />.
      </p>
    </main>
  );
}
