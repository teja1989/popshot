"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { apiDelete, ApiError } from "@/lib/api-client";
import { labelFor, wantsReflection, type FocusOption, type Reflection } from "@/lib/focus";
import { namesOn, playedWhen, type Match } from "@/lib/games";
import type { GroupSummary } from "@/lib/groups";
import type { Team } from "@/lib/scoring";

import { recall, remember } from "@/lib/remember";

import { useSignedIn } from "./auth";
import { EventsSection } from "./events-section";
import { GamesCalendar } from "./games-calendar";
import { GroupScoped } from "./group-scoped";
import { PlayNightsSection } from "./play-nights-section";
import { ReflectionSheet } from "./reflection-sheet";
import { Fab } from "./ui/fab";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";
import { CourtArt } from "./ui/court-art";
import { LockIcon } from "./ui/icons";
import { segmentOption, segmentTrack } from "./ui/segmented";

type View = "list" | "calendar";
const VIEWS: readonly View[] = ["list", "calendar"];
const VIEW_KEY = "popshot.games.view";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

/**
 * Play: everything about getting on court for the chosen crew. Its meetups, logging a game,
 * and the games so far as a list or a calendar.
 */
export function PlayView() {
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
    <GroupScoped title="Play">
      {(group) => (
        <GroupGames key={group.id} group={group} justLogged={arrival.logged} reflectFirst={arrival.reflect} />
      )}
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
  const [view, setView] = useState<View>(() => recall(VIEW_KEY, VIEWS, "list"));
  // A game opened for reflecting from the calendar, and how to refresh the calendar after.
  const [fromCalendar, setFromCalendar] = useState<{ match: Match; reload: () => void } | null>(null);

  function saved(matchId: string, reflection: Reflection) {
    if (result.kind === "ready") {
      replace(result.data.map((m) => (m.id === matchId ? { ...m, my_reflection: reflection } : m)));
    }
    setReflecting(null);
  }

  return (
    <>
      <PlayNightsSection groupId={group.id} />

      <EventsSection group={group} />

      {justLogged && (
        <p role="status" className="animate-rise rounded-xl bg-chip px-4 py-3 text-body font-bold">
          Game logged. It&apos;s on your crew&apos;s record now, and you can edit it any time.
        </p>
      )}

      <fieldset className={`${segmentTrack} grid-cols-2`}>
        <legend className="sr-only">Show games as</legend>
        {VIEWS.map((value) => (
          <label key={value} className={segmentOption}>
            <input
              type="radio"
              name="games-view"
              checked={view === value}
              onChange={() => {
                remember(VIEW_KEY, value);
                setView(value);
              }}
              className="sr-only"
            />
            {value === "list" ? "List" : "Calendar"}
          </label>
        ))}
      </fieldset>

      {view === "calendar" && (
        <GamesCalendar
          group={group}
          renderGame={(match, reloadCalendar) => (
            <GameCard
              key={match.id}
              groupId={group.id}
              match={match}
              labels={labels}
              onDeleted={() => {
                reloadCalendar();
                reload();
              }}
              onReflect={() => {
                setFromCalendar({ match, reload: reloadCalendar });
              }}
            />
          )}
        />
      )}

      {view === "list" && result.kind === "loading" && <p className="text-muted">Loading games…</p>}

      {view === "list" && result.kind === "error" && (
        <div
          role="alert"
          className="flex flex-col items-start gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-5"
        >
          <p>We couldn&apos;t load the games just now.</p>
          <button type="button" className={buttonClass("quiet")} onClick={reload}>
            Try again
          </button>
        </div>
      )}

      {view === "list" && result.kind === "ready" && result.data.length === 0 && (
        <section className="flex animate-rise flex-col gap-4 rounded-3xl border border-transparent bg-surface shadow-card p-5">
          <CourtArt className="w-40" />
          <h2 className="text-title-sm font-extrabold">No games in {group.name} yet</h2>
          <p className="text-lead leading-relaxed text-muted">
            Log your first one: pick who played and tap in the score. It counts right away, and you can fix it later if
            needed.
          </p>
        </section>
      )}

      {view === "list" && result.kind === "ready" && result.data.length > 0 && (
        <section aria-labelledby="recent-heading" className="flex animate-rise flex-col gap-2">
          <h2 id="recent-heading" className="text-title-sm font-bold text-ink">
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
          {result.data.length >= 50 && <p className="text-small text-muted">Showing the latest 50 games.</p>}
        </section>
      )}

      {fromCalendar?.match.i_played && (
        <ReflectionSheet
          groupId={group.id}
          match={fromCalendar.match}
          open
          onOpenChange={(open) => {
            if (!open) {
              setFromCalendar(null);
            }
          }}
          onSaved={() => {
            fromCalendar.reload();
            reload();
            setFromCalendar(null);
          }}
        />
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
      <Fab href={`/groups/${group.id}/log`} label="Log a game" />
    </>
  );
}

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
  const canChange = match.can_edit;

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
    <li className="flex flex-col gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="text-small text-muted">{playedWhen(match.played_at)}</span>
        <span className="text-meta text-muted">
          {match.format === "doubles" ? "Doubles" : "Singles"} · to {match.points_to}
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
                <th
                  scope="row"
                  className={`w-full truncate pr-3 text-left text-lead ${won ? "font-extrabold" : "font-normal text-muted"}`}
                >
                  <span className="flex items-center gap-2">
                    <span
                      aria-hidden="true"
                      className={`size-2 shrink-0 rounded-full ${won ? "bg-ball" : "bg-transparent"}`}
                    />
                    <span className="truncate">{namesOn(match, team)}</span>
                  </span>
                </th>
                {match.games.map((game, index) => {
                  const mine = team === "A" ? game.team_a : game.team_b;
                  const theirs = team === "A" ? game.team_b : game.team_a;
                  return (
                    <td
                      key={index}
                      className={`min-w-8 pl-3 text-right text-title leading-none tabular-nums font-numeral ${mine > theirs ? "font-extrabold" : "text-muted"}`}
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
      <div className="flex flex-wrap items-center justify-between gap-2 text-meta text-muted">
        <span>{match.entered_by_name ? `Logged by ${match.entered_by_me ? "you" : match.entered_by_name}` : ""}</span>
        {canChange && !confirming && (
          <span className="flex">
            <Link
              href={`/groups/${groupId}/matches/${match.id}/edit`}
              aria-label="Edit game"
              className="flex min-h-11 items-center px-2 font-bold text-primary no-underline"
            >
              Edit
            </Link>
            <button
              type="button"
              className="min-h-11 cursor-pointer px-2 font-bold text-primary"
              onClick={() => {
                setConfirming(true);
              }}
            >
              Delete
            </button>
          </span>
        )}
      </div>
      {wantsReflection(match) && (
        <button
          type="button"
          onClick={onReflect}
          className="flex min-h-12 cursor-pointer items-center justify-between gap-3 rounded-xl bg-chip px-4 text-left text-body font-bold"
        >
          <span>How did it go for you?</span>
          <span className="text-meta font-semibold text-muted">Optional · 2 taps</span>
        </button>
      )}
      {match.my_reflection && <MyNotes reflection={match.my_reflection} labels={labels} onEdit={onReflect} />}
      {confirming && (
        <div className="flex flex-col gap-3 rounded-xl border border-warn p-3">
          <p className="text-body font-bold">Delete this game? It comes off everyone&apos;s record.</p>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              className={buttonClass("quiet", "min-h-11 text-body")}
              onClick={() => {
                setConfirming(false);
              }}
            >
              Keep
            </button>
            <button
              type="button"
              className={buttonClass("danger", "min-h-11 text-body")}
              disabled={busy}
              onClick={() => void remove()}
            >
              Delete game
            </button>
          </div>
        </div>
      )}
      <p role="alert" className="text-small text-warn empty:hidden">
        {problem}
      </p>
    </li>
  );
}

/** Your own notes on a game. Only ever sent to you. */
function MyNotes({
  reflection,
  labels,
  onEdit,
}: {
  reflection: Reflection;
  labels: FocusOption[];
  onEdit: () => void;
}) {
  const skipped = reflection.went_well.length === 0 && reflection.to_improve.length === 0;
  const names = (ids: string[]) => ids.map((id) => labelFor(labels, id)).join(", ");
  return (
    <div className="flex items-start justify-between gap-3 text-meta text-muted">
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
