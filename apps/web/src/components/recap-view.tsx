"use client";

import Link from "next/link";

import { namesOn, playedWhen, scoreLine, type Match } from "@/lib/games";
import { describeAward, outingSize, outingWindow, type Recap } from "@/lib/recaps";

import { ShareRecap } from "./share-recap";
import { useApiGet } from "./use-api";
import { Avatar } from "./ui/avatar";
import { buttonClass } from "./ui/button";
import { CourtPattern } from "./ui/court-pattern";
import { BackIcon } from "./ui/icons";

// Written out so Tailwind sees them: the awards come in one after another.
const STAGGER = [
  "",
  "[animation-delay:90ms]",
  "[animation-delay:180ms]",
  "[animation-delay:270ms]",
  "[animation-delay:360ms]",
  "[animation-delay:450ms]",
];

/** One outing's recap: the story, the awards, who played and the games. */
export function RecapView({ groupId, recapKey }: { groupId: string; recapKey: string }) {
  const { result, reload } = useApiGet<Recap>(`/v1/groups/${groupId}/recaps/${recapKey}`);

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-5 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <Link
        href="/crew"
        className="-ml-1 flex min-h-11 items-center gap-1.5 self-start text-[15px] font-bold text-primary no-underline"
      >
        <BackIcon />
        Crew
      </Link>

      {result.kind === "loading" && <p className="text-muted">Loading the recap…</p>}
      {result.kind === "error" && result.status === 404 && (
        <h1 className="text-[26px] font-extrabold">We couldn&apos;t find that recap.</h1>
      )}
      {result.kind === "error" && result.status !== 404 && (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-2xl border border-line bg-surface p-5">
          <p>We couldn&apos;t load this recap just now.</p>
          <button type="button" className={buttonClass("quiet")} onClick={reload}>
            Try again
          </button>
        </div>
      )}
      {result.kind === "ready" && <RecapBody groupId={groupId} recap={result.data} />}
    </main>
  );
}

function RecapBody({ groupId, recap }: { groupId: string; recap: Recap }) {
  return (
    <>
      <section className="relative isolate flex animate-rise flex-col gap-3 overflow-hidden rounded-[28px] bg-hero p-6 text-on-hero">
        <CourtPattern />
        <p className="text-[14px] font-bold text-on-hero-muted">
          {playedWhen(recap.start)}
          {recap.venue ? ` · ${recap.venue}` : ""} · {outingSize(recap)}
        </p>
        <h1 className="text-[28px] leading-[1.1] font-extrabold tracking-[-0.01em] [font-stretch:108%]">
          {recap.headline}
        </h1>
        <ul className="flex flex-col gap-2 text-[17px] leading-snug">
          {recap.lines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        {recap.written_by === "ai" && (
          <p className="text-[13px] font-bold text-on-hero-muted">Written by AI (Google Gemini) from your games.</p>
        )}
      </section>

      <ShareRecap groupId={groupId} recapKey={recap.key} headline={recap.headline} />

      {recap.awards.length > 0 && (
        <section aria-labelledby="awards-heading" className="flex flex-col gap-2">
          <h2 id="awards-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
            Awards
          </h2>
          <ul className="grid gap-2 sm:grid-cols-2">
            {recap.awards.map((award, i) => {
              const { title, why } = describeAward(award);
              return (
                <li
                  key={`${award.kind}-${award.players.map((p) => p.player_id).join()}`}
                  className={`flex animate-rise flex-col gap-1 rounded-2xl border border-line bg-surface p-4 ${STAGGER[Math.min(i, STAGGER.length - 1)] ?? ""}`}
                >
                  <span className="flex items-center gap-2 text-[17px] font-extrabold">
                    <span aria-hidden="true" className="size-2.5 rounded-full bg-ball" />
                    {title}
                  </span>
                  <span className="text-[16px] font-bold">{award.players.map((p) => p.display_name).join(", ")}</span>
                  <span className="text-[14px] text-muted">{why}</span>
                </li>
              );
            })}
          </ul>
        </section>
      )}

      <section aria-labelledby="played-heading" className="flex flex-col gap-2">
        <h2 id="played-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
          Who played
        </h2>
        <ul className="flex flex-wrap gap-2">
          {recap.played.map(({ player, games }) => (
            <li
              key={player.player_id}
              className="flex items-center gap-2 rounded-full border border-line bg-surface py-1 pr-3 pl-1"
            >
              <Avatar name={player.display_name} size="sm" />
              <span className="text-[15px] font-bold">{player.display_name}</span>
              <span className="text-[14px] text-muted">{games}</span>
            </li>
          ))}
        </ul>
      </section>

      <OutingGames groupId={groupId} recap={recap} />
    </>
  );
}

function OutingGames({ groupId, recap }: { groupId: string; recap: Recap }) {
  const { start, end } = outingWindow(recap);
  const { result } = useApiGet<{ games: Match[] }>(
    `/v1/groups/${groupId}/calendar?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`,
  );
  if (result.kind !== "ready") {
    return null;
  }
  const games = result.data.games.filter((m) => recap.match_ids.includes(m.id));
  return (
    <section aria-labelledby="games-heading" className="flex flex-col gap-2">
      <h2 id="games-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
        The games
      </h2>
      <ol className="overflow-hidden rounded-2xl border border-line bg-surface">
        {games.map((m) => (
          <li key={m.id} className="flex flex-col gap-0.5 border-b border-line px-4 py-3 last:border-b-0">
            <span className="text-[16px] font-bold">{namesOn(m, m.winner)}</span>
            <span className="text-[15px] text-muted">
              {scoreLine(m)} · vs {namesOn(m, m.winner === "A" ? "B" : "A")}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}
