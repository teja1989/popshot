"use client";

import Link from "next/link";

import { change, everyone, points, type Board, type BoardRow } from "@/lib/board";

import { CrewHighlights } from "./crew-highlights";
import { CrewPointsInfo } from "./crew-points-info";
import { GroupScoped } from "./group-scoped";
import { RecapCard } from "./recap-card";
import { useApiGet } from "./use-api";
import { Avatar } from "./ui/avatar";
import { buttonClass } from "./ui/button";

// The Crew tab: what's worth celebrating lately, everyone in the crew (A to Z, never
// ranked), and your own crew points.

export function CrewView() {
  return <GroupScoped title="Crew">{(group) => <GroupCrew key={group.id} groupId={group.id} />}</GroupScoped>;
}

function GroupCrew({ groupId }: { groupId: string }) {
  const { result, reload } = useApiGet<Board>(`/v1/groups/${groupId}/board`);
  if (result.kind === "loading") {
    return <p className="text-muted">Loading your crew…</p>;
  }
  if (result.kind === "error") {
    return (
      <div role="alert" className="flex flex-col items-start gap-3 rounded-2xl border border-line bg-surface p-5">
        <p>We couldn&apos;t load your crew just now.</p>
        <button type="button" className={buttonClass("quiet")} onClick={reload}>
          Try again
        </button>
      </div>
    );
  }
  const people = everyone(result.data);
  const me = people.find((row) => row.is_me && row.matches > 0);
  const noGames = people.every((row) => row.matches === 0);

  return (
    <>
      <RecapCard groupId={groupId} />

      <CrewHighlights groupId={groupId} />

      {noGames && (
        <section className="flex animate-rise flex-col items-start gap-3 rounded-2xl border border-line bg-surface p-5">
          <h2 className="text-title-sm font-extrabold">No games yet</h2>
          <p className="text-lead leading-relaxed text-muted">
            Log your first game and this is where the crew&apos;s streaks, partnerships and welcomes show up.
          </p>
          <Link href={`/groups/${groupId}/log`} className={buttonClass("action")}>
            Log a game
          </Link>
        </section>
      )}

      {me && <MyPoints row={me} />}

      <section aria-labelledby="everyone-heading" className="flex animate-rise flex-col gap-2 [animation-delay:60ms]">
        <h2 id="everyone-heading" className="text-label font-bold tracking-[0.1em] text-muted uppercase">
          Everyone · {people.length}
        </h2>
        <ul aria-labelledby="everyone-heading" className="overflow-hidden rounded-2xl border border-line bg-surface">
          {people.map((row) => (
            <li
              key={row.player_id}
              className={`flex min-h-14 items-center gap-3 border-b border-line px-4 py-2 last:border-b-0 ${row.is_me ? "bg-chip" : ""}`}
            >
              <Avatar name={row.display_name} photoUrl={row.avatar_url} size="sm" />
              <span className="min-w-0 grow truncate text-lead font-bold">
                {row.display_name}
                {row.is_me && <span className="font-normal text-muted"> (you)</span>}
                {row.is_guest && <span className="text-meta font-semibold text-muted"> · guest</span>}
              </span>
              <span className="shrink-0 text-small text-muted tabular-nums">
                {row.matches === 1 ? "1 game" : `${String(row.matches)} games`}
              </span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}

function MyPoints({ row }: { row: BoardRow }) {
  const moved = change(row.week_change);
  return (
    <section
      aria-labelledby="my-points-heading"
      className="flex animate-rise flex-col gap-2 rounded-2xl border border-line bg-surface p-4"
    >
      <div className="flex items-center gap-0.5">
        <h2 id="my-points-heading" className="text-label font-bold tracking-[0.1em] text-muted uppercase">
          Your crew points
        </h2>
        <CrewPointsInfo />
      </div>
      <p className="flex items-baseline gap-3">
        <span className="text-display-sm leading-none font-extrabold tabular-nums font-numeral">
          {points(row.rating)}
        </span>
        {moved && (
          <span className={`text-small font-bold ${moved.up ? "text-win" : "text-muted"}`}>
            {moved.text} this week
          </span>
        )}
      </p>
      <p className="text-small text-muted">
        {row.to_go > 0
          ? `Still settling: ${String(row.to_go)} more game${row.to_go === 1 ? "" : "s"} and they reflect how you play.`
          : `They help keep games even. Your crew isn't ranked.`}
      </p>
    </section>
  );
}
