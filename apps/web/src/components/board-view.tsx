"use client";

import Link from "next/link";

import { change, points, winRate, type Board, type BoardRow } from "@/lib/board";

import { GroupScoped } from "./group-scoped";
import { HighlightsStrip } from "./highlights-strip";
import { useApiGet } from "./use-api";
import { Avatar } from "./ui/avatar";
import { buttonClass } from "./ui/button";

export function BoardView() {
  return <GroupScoped title="Board">{(group) => <GroupBoard key={group.id} groupId={group.id} />}</GroupScoped>;
}

function GroupBoard({ groupId }: { groupId: string }) {
  const { result, reload } = useApiGet<Board>(`/v1/groups/${groupId}/board`);
  if (result.kind === "loading") {
    return <p className="text-muted">Loading the board…</p>;
  }
  if (result.kind === "error") {
    return (
      <div role="alert" className="flex flex-col items-start gap-3 rounded-2xl border border-line bg-surface p-5">
        <p>We couldn&apos;t load the board just now.</p>
        <button type="button" className={buttonClass("quiet")} onClick={reload}>
          Try again
        </button>
      </div>
    );
  }
  const board = result.data;
  const nobodyRanked = board.ranked.length === 0;

  return (
    <>
      <HighlightsStrip groupId={groupId} />

      {nobodyRanked && (
        <section className="flex animate-rise flex-col items-start gap-3 rounded-2xl border border-line bg-surface p-5">
          <h2 className="text-[20px] font-extrabold">Nobody&apos;s ranked yet</h2>
          <p className="text-[16px] leading-relaxed text-muted">
            Players join the ranking after {board.ranked_after} games. Every game counts, so keep logging.
          </p>
          <Link href={`/groups/${groupId}/log`} className={buttonClass("action")}>
            Log a game
          </Link>
        </section>
      )}

      {!nobodyRanked && (
        <section aria-labelledby="ranked-heading" className="flex animate-rise flex-col gap-2">
          <h2 id="ranked-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
            Ranked · crew points
          </h2>
          <ol aria-labelledby="ranked-heading" className="overflow-hidden rounded-2xl border border-line bg-surface">
            {board.ranked.map((row) => (
              <RankedRow key={row.player_id} row={row} />
            ))}
          </ol>
        </section>
      )}

      {board.getting_started.length > 0 && (
        <section aria-labelledby="starting-heading" className="flex animate-rise flex-col gap-2 [animation-delay:60ms]">
          <h2 id="starting-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
            Getting started · {board.ranked_after} games to be ranked
          </h2>
          <ul aria-labelledby="starting-heading" className="overflow-hidden rounded-2xl border border-line bg-surface">
            {board.getting_started.map((row) => (
              <StartingRow key={row.player_id} row={row} need={board.ranked_after} />
            ))}
          </ul>
        </section>
      )}

      {board.resting.length > 0 && (
        <section aria-labelledby="resting-heading" className="flex animate-rise flex-col gap-2 [animation-delay:120ms]">
          <h2 id="resting-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
            Resting · no games in {board.resting_after_days} days
          </h2>
          <ul aria-labelledby="resting-heading" className="overflow-hidden rounded-2xl border border-line bg-surface">
            {board.resting.map((row) => (
              <li key={row.player_id} className="flex min-h-14 items-center gap-3 border-b border-line px-4 py-2 last:border-b-0">
                <Avatar name={row.display_name} photoUrl={row.avatar_url} size="sm" />
                <Name row={row} />
                <span className="text-[18px] font-extrabold text-muted tabular-nums [font-stretch:75%]">{points(row.rating)}</span>
              </li>
            ))}
          </ul>
          <p className="text-[14px] text-muted">One game puts them back in the ranking.</p>
        </section>
      )}

      <p className="text-[14px] leading-relaxed text-muted">
        Crew points run from 2.00 to 6.00. Every game moves them by the share of points you won
        compared with what the ratings expected, so a close win over a stronger team counts for
        more. They compare you with this crew, not with anyone else.
      </p>
    </>
  );
}

function Name({ row }: { row: BoardRow }) {
  return (
    <span className="min-w-0 grow truncate text-[16px] font-bold">
      {row.display_name}
      {row.is_me && <span className="font-normal text-muted"> (you)</span>}
      {row.is_guest && <span className="text-[12px] font-semibold text-muted"> · guest</span>}
    </span>
  );
}

function RankedRow({ row }: { row: BoardRow }) {
  const moved = change(row.week_change);
  return (
    <li className={`flex flex-col gap-2 border-b border-line px-4 py-3 last:border-b-0 ${row.is_me ? "bg-chip" : ""}`}>
      <div className="flex items-center gap-3">
        <span className={`w-6 text-center text-[22px] font-extrabold tabular-nums [font-stretch:72%] ${row.rank === 1 ? "text-ink" : "text-muted"}`}>
          {row.rank}
        </span>
        <Avatar name={row.display_name} photoUrl={row.avatar_url} tone={row.rank === 1 ? "ball" : "chip"} />
        <Name row={row} />
        <span className="flex flex-col items-end">
          <span className="text-[24px] leading-none font-extrabold tabular-nums [font-stretch:75%]">{points(row.rating)}</span>
          {moved && (
            <span className={`text-[12px] font-bold ${moved.up ? "text-win" : "text-loss"}`}>
              {moved.text}
              <span className="sr-only"> this week</span>
            </span>
          )}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 pl-9 text-[13px] text-muted">
        <span>
          {winRate(row)} won · {row.matches} games
        </span>
        <Form form={row.form} />
        <Reliability value={row.reliability} />
      </div>
    </li>
  );
}

function StartingRow({ row, need }: { row: BoardRow; need: number }) {
  const done = need - row.to_go;
  return (
    <li className={`flex min-h-16 items-center gap-3 border-b border-line px-4 py-3 last:border-b-0 ${row.is_me ? "bg-chip" : ""}`}>
      <Avatar name={row.display_name} photoUrl={row.avatar_url} size="sm" />
      <span className="flex min-w-0 grow flex-col gap-1">
        <Name row={row} />
        <span className="flex items-center gap-2 text-[13px] text-muted">
          <Bar percent={(100 * done) / need} className="w-20" />
          {done} of {need} games
        </span>
      </span>
      {row.matches > 0 && (
        <span className="text-[18px] font-extrabold text-muted tabular-nums [font-stretch:75%]">{points(row.rating)}</span>
      )}
    </li>
  );
}

function Form({ form }: { form: ("W" | "L")[] }) {
  if (form.length === 0) {
    return null;
  }
  return (
    <span className="flex items-center gap-1" aria-label={`Last ${String(form.length)}, newest first: ${form.join(" ")}`}>
      {form.map((r, i) => (
        <span
          key={i}
          aria-hidden="true"
          className={
            r === "W"
              ? "flex size-5 items-center justify-center rounded bg-win text-[10px] font-extrabold text-on-win"
              : "flex size-5 items-center justify-center rounded border border-dashed border-loss text-[10px] font-extrabold text-muted"
          }
        >
          {r}
        </span>
      ))}
    </span>
  );
}

function Reliability({ value }: { value: number }) {
  return (
    <span className="flex items-center gap-1.5">
      <Bar percent={value} className="w-12" />
      {value}% reliable
    </span>
  );
}

/** A small progress bar. SVG, so the width is an attribute rather than an inline style. */
function Bar({ percent, className }: { percent: number; className: string }) {
  const width = Math.max(0, Math.min(100, percent));
  return (
    <svg className={`h-1.5 overflow-hidden rounded-full ${className}`} aria-hidden="true" preserveAspectRatio="none" viewBox="0 0 100 6">
      <rect width="100" height="6" className="fill-line" />
      <rect width={width} height="6" className="fill-primary" />
    </svg>
  );
}
