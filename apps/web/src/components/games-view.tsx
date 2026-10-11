"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { apiDelete, ApiError } from "@/lib/api-client";
import { labelFor, wantsReflection, type FocusOption, type Reflection } from "@/lib/focus";
import { namesOn, playedWhen, STATUS_LABEL, type Match } from "@/lib/games";
import type { GroupSummary } from "@/lib/groups";
import type { Team } from "@/lib/scoring";

import { useSignedIn } from "./auth";
import { GroupScoped } from "./group-scoped";
import { ReflectionSheet } from "./reflection-sheet";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";
import { CourtArt } from "./ui/court-art";
import { LockIcon, PlusIcon } from "./ui/icons";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export function GamesView() {
  // After logging a game: "?logged=1", plus "&reflect=<id>" when you played in it. Read
  // once, then tidy the address so a reload doesn't repeat them.
  const [arrival] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const reflect = params.get("reflect");
    return { logged: params.has("logged"), reflect: reflect && UUID.test(reflect) ? reflect : null };
  });
  useEffect(() => {
    if (window.location.search) {
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, []);

  return (
    <GroupScoped title="Games">
      {(group) => <GroupGames key={group.id} group={group} justLogged={arrival.logged} reflectFirst={arrival.reflect} />}
    </GroupScoped>
  );
}

function GroupGames({
  group,
  justLogged,
  reflectFirst,
}: {
  group: GroupSummary;
  justLogged: boolean;
  reflectFirst: string | null;
}) {
  const { result, reload, replace } = useApiGet<Match[]>(`/v1/groups/${group.id}/matches`);
  const options = useApiGet<FocusOption[]>("/v1/focus-options");
  // The game whose reflection sheet is open. Right after logging, the one you just played.
  const [reflecting, setReflecting] = useState<string | null>(reflectFirst);
  const reflectingMatch = result.kind === "ready" ? result.data.find((m) => m.id === reflecting) : undefined;
  const labels = options.result.kind === "ready" ? options.result.data : [];

  function saved(matchId: string, reflection: Reflection) {
    if (result.kind === "ready") {
      replace(result.data.map((m) => (m.id === matchId ? { ...m, my_reflection: reflection } : m)));
    }
    setReflecting(null);
  }

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
              <GameCard
                key={match.id}
                groupId={group.id}
                match={match}
                labels={labels}
                onDeleted={reload}
                onReflect={() => {
                  setReflecting(match.id);
                }}
              />
            ))}
          </ul>
          {result.data.length >= 50 && <p className="text-[14px] text-muted">Showing the latest 50 games.</p>}
        </section>
      )}

      {reflectingMatch?.i_played && (
        <ReflectionSheet
          groupId={group.id}
          match={reflectingMatch}
          open
          onOpenChange={(open) => {
            if (!open) {
              setReflecting(null);
            }
          }}
          onSaved={(reflection) => {
            saved(reflectingMatch.id, reflection);
          }}
        />
      )}
    </>
  );
}

const STATUS_TONE: Record<Match["status"], string> = {
  pending: "bg-chip text-muted",
  confirmed: "bg-win text-on-win",
  disputed: "border border-warn text-warn",
};

function GameCard({
  groupId,
  match,
  labels,
  onDeleted,
  onReflect,
}: {
  groupId: string;
  match: Match;
  labels: FocusOption[];
  onDeleted: () => void;
  onReflect: () => void;
}) {
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
      {wantsReflection(match) && (
        <button
          type="button"
          onClick={onReflect}
          className="flex min-h-12 cursor-pointer items-center justify-between gap-3 rounded-xl bg-chip px-4 text-left text-[15px] font-bold"
        >
          <span>How did it go for you?</span>
          <span className="text-[13px] font-semibold text-muted">Optional · 2 taps</span>
        </button>
      )}
      {match.my_reflection && <MyNotes reflection={match.my_reflection} labels={labels} onEdit={onReflect} />}
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

/** Your own notes on a game. Only ever sent to you. */
function MyNotes({ reflection, labels, onEdit }: { reflection: Reflection; labels: FocusOption[]; onEdit: () => void }) {
  const skipped = reflection.went_well.length === 0 && reflection.to_improve.length === 0;
  const names = (ids: string[]) => ids.map((id) => labelFor(labels, id)).join(", ");
  return (
    <div className="flex items-start justify-between gap-3 text-[13px] text-muted">
      <p className="flex items-start gap-1.5">
        <span className="mt-0.5 shrink-0">
          <LockIcon />
        </span>
        <span>
          {skipped ? (
            "No notes for this game."
          ) : (
            <>
              {reflection.went_well.length > 0 && <>Went well: {names(reflection.went_well)}. </>}
              {reflection.to_improve.length > 0 && <>To improve: {names(reflection.to_improve)}.</>}
            </>
          )}
        </span>
      </p>
      <button type="button" className="min-h-11 shrink-0 cursor-pointer px-2 font-bold text-primary" onClick={onEdit}>
        {skipped ? "Add notes" : "Edit notes"}
      </button>
    </div>
  );
}
