"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { apiDelete, ApiError } from "@/lib/api-client";
import { namesOn, playedWhen, STATUS_LABEL, type Match } from "@/lib/games";
import type { GroupSummary } from "@/lib/groups";
import type { Team } from "@/lib/scoring";

import { useSignedIn } from "./auth";
import { GroupScoped } from "./group-scoped";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";
import { CourtArt } from "./ui/court-art";
import { PlusIcon } from "./ui/icons";

export function GamesView() {
  // "?logged=1" after logging a game: say so once, then tidy the address.
  const [justLogged] = useState(() => new URLSearchParams(window.location.search).has("logged"));
  useEffect(() => {
    if (justLogged) {
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, [justLogged]);

  return (
    <GroupScoped title="Games">
      {(group) => <GroupGames key={group.id} group={group} justLogged={justLogged} />}
    </GroupScoped>
  );
}

function GroupGames({ group, justLogged }: { group: GroupSummary; justLogged: boolean }) {
  const { result, reload } = useApiGet<Match[]>(`/v1/groups/${group.id}/matches`);

  return (
    <>
      <Link href={`/groups/${group.id}/log`} className={buttonClass("action", "h-14")}>
        <PlusIcon />
        Log a game
      </Link>

      {justLogged && (
        <p role="status" className="animate-rise rounded-xl bg-chip px-4 py-3 text-[15px] font-bold">
          Game logged. It shows as waiting until someone on the other team confirms it.
        </p>
      )}

      {result.kind === "loading" && <p className="text-muted">Loading games…</p>}

      {result.kind === "error" && (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-2xl border border-line bg-surface p-5">
          <p>We couldn&apos;t load the games just now.</p>
          <button type="button" className={buttonClass("quiet")} onClick={reload}>
            Try again
          </button>
        </div>
      )}

      {result.kind === "ready" && result.data.length === 0 && (
        <section className="flex animate-rise flex-col gap-4 rounded-2xl border border-line bg-surface p-5">
          <CourtArt className="w-40" />
          <h2 className="text-[20px] font-extrabold">No games in {group.name} yet</h2>
          <p className="text-[16px] leading-relaxed text-muted">
            Log your first one: pick who played, tap in the score, and someone on the other team
            confirms it.
          </p>
        </section>
      )}

      {result.kind === "ready" && result.data.length > 0 && (
        <section aria-labelledby="recent-heading" className="flex animate-rise flex-col gap-2">
          <h2 id="recent-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
            Recent games
          </h2>
          <ul className="flex flex-col gap-3">
            {result.data.map((match) => (
              <GameCard key={match.id} groupId={group.id} match={match} onDeleted={reload} />
            ))}
          </ul>
          {result.data.length >= 50 && <p className="text-[14px] text-muted">Showing the latest 50 games.</p>}
        </section>
      )}
    </>
  );
}

const STATUS_TONE: Record<Match["status"], string> = {
  pending: "bg-chip text-muted",
  confirmed: "bg-win text-on-win",
  disputed: "border border-warn text-warn",
};

function GameCard({ groupId, match, onDeleted }: { groupId: string; match: Match; onDeleted: () => void }) {
  const { user } = useSignedIn();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const canDelete = match.entered_by_me && match.status === "pending";

  async function remove() {
    setBusy(true);
    setProblem(null);
    try {
      await apiDelete(user, `/v1/groups/${groupId}/matches/${match.id}`);
      onDeleted();
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "We couldn't delete it just now.");
      setBusy(false);
    }
  }

  return (
    <li className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="text-[14px] text-muted">{playedWhen(match.played_at)}</span>
        <span className={`rounded-full px-2.5 py-1 text-[12px] font-bold ${STATUS_TONE[match.status]}`}>
          {STATUS_LABEL[match.status]}
        </span>
      </div>
      <table className="w-full border-separate border-spacing-y-1">
        <caption className="sr-only">
          {namesOn(match, match.winner)} beat {namesOn(match, match.winner === "A" ? "B" : "A")}
        </caption>
        <tbody>
          {(["A", "B"] as Team[]).map((team) => {
            const won = match.winner === team;
            return (
              <tr key={team}>
                <th scope="row" className={`w-full truncate pr-3 text-left text-[16px] ${won ? "font-extrabold" : "font-normal text-muted"}`}>
                  <span className="flex items-center gap-2">
                    <span aria-hidden="true" className={`size-2 shrink-0 rounded-full ${won ? "bg-ball" : "bg-transparent"}`} />
                    <span className="truncate">{namesOn(match, team)}</span>
                  </span>
                </th>
                {match.games.map((game, index) => {
                  const mine = team === "A" ? game.team_a : game.team_b;
                  const theirs = team === "A" ? game.team_b : game.team_a;
                  return (
                    <td
                      key={index}
                      className={`min-w-8 pl-3 text-right text-[22px] leading-none tabular-nums [font-stretch:75%] ${mine > theirs ? "font-extrabold" : "text-muted"}`}
                    >
                      {mine}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="flex flex-wrap items-center justify-between gap-2 text-[13px] text-muted">
        <span>
          {match.format === "doubles" ? "Doubles" : "Singles"} · to {match.points_to}
          {match.entered_by_name ? ` · logged by ${match.entered_by_me ? "you" : match.entered_by_name}` : ""}
        </span>
        {canDelete && !confirming && (
          <button
            type="button"
            className="min-h-11 cursor-pointer px-2 font-bold text-primary"
            onClick={() => {
              setConfirming(true);
            }}
          >
            Delete
          </button>
        )}
      </div>
      {confirming && (
        <div className="flex flex-col gap-3 rounded-xl border border-warn p-3">
          <p className="text-[15px] font-bold">Delete this game? Use this for a typo, then log it again.</p>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              className={buttonClass("quiet", "min-h-11 text-[15px]")}
              onClick={() => {
                setConfirming(false);
              }}
            >
              Keep
            </button>
            <button type="button" className={buttonClass("danger", "min-h-11 text-[15px]")} disabled={busy} onClick={() => void remove()}>
              Delete game
            </button>
          </div>
        </div>
      )}
      <p role="alert" className="text-[14px] text-warn empty:hidden">
        {problem}
      </p>
    </li>
  );
}
