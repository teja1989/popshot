"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { apiGet, apiPost, apiPut, ApiError } from "@/lib/api-client";
import {
  formatInfo,
  MAX_PLAYERS,
  myResultsLine,
  pointDifference,
  scoreText,
  teamLine,
  type CrewEvent,
  type EventCourt,
  type EventRound,
} from "@/lib/events";
import type { Player } from "@/lib/games";
import { gamesToShow, validateMatch, type GameRules, type Team } from "@/lib/scoring";

import { AddGuestInline } from "./add-guest-inline";
import { useSignedIn } from "./auth";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";

// How often an open event looks for scores entered on other phones.
const REFRESH_MS = 10_000;

/** One event, live: a card per court, who's sitting out, and the lead's controls. */
export function EventView({ groupId, eventId }: { groupId: string; eventId: string }) {
  const { user } = useSignedIn();
  const path = `/v1/groups/${groupId}/events/${eventId}` as const;
  const { result, replace } = useApiGet<CrewEvent>(path);
  const event = result.kind === "ready" ? result.data : null;
  const live = event?.status === "live";

  // Scores come in from other phones: look again every few seconds, and when you come back.
  useEffect(() => {
    if (!live) {
      return;
    }
    const refresh = () => {
      if (document.visibilityState === "visible") {
        apiGet<CrewEvent>(user, path)
          .then(replace)
          .catch(() => {
            // Keep showing what we have; the next look will try again.
          });
      }
    };
    const timer = window.setInterval(refresh, REFRESH_MS);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [live, user, path, replace]);

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <Link href="/play" className="self-start text-small font-bold text-primary">
        ← Play
      </Link>
      {result.kind === "loading" && <p className="text-muted">Loading the event…</p>}
      {result.kind === "error" && (
        <p role="alert" className="text-warn">
          {result.status === 404 ? "We couldn't find that event." : "We couldn't load the event just now."}
        </p>
      )}
      {event && <Event groupId={groupId} event={event} onChange={replace} />}
    </main>
  );
}

function Event({
  groupId,
  event,
  onChange,
}: {
  groupId: string;
  event: CrewEvent;
  onChange: (event: CrewEvent) => void;
}) {
  const { user } = useSignedIn();
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [confirmFinish, setConfirmFinish] = useState(false);
  const names = useMemo(() => new Map(event.people.map((p) => [p.player_id, p.display_name])), [event.people]);
  const base = `/v1/groups/${groupId}/events/${event.id}` as const;
  const info = formatInfo(event.kind);
  const live = event.status === "live";
  const rounds = [...event.round_list].reverse();
  const rules: GameRules = { pointsTo: event.points_to, winByTwo: event.win_by_two };

  async function act(call: () => Promise<CrewEvent>) {
    setBusy(true);
    setProblem(null);
    try {
      onChange(await call());
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "That didn't go through just now.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <header className="flex flex-col gap-1">
        <h1 className="text-display-sm leading-tight font-extrabold tracking-[-0.02em] break-words font-display">
          {event.name}
        </h1>
        <p className="text-body text-muted">
          {/* The format's name only when the event has a name of its own. */}
          {event.name === info.name ? "" : `${info.name} · `}
          {info.standard} · {event.vibe === "social" ? "Social" : "Competitive"}
          {live ? "" : " · Finished"}
        </p>
      </header>

      {event.can_manage && live && (
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled={!event.can_start_round || busy}
            className={buttonClass("action", "h-12")}
            onClick={() => void act(() => apiPost<CrewEvent>(user, `${base}/rounds`, {}))}
          >
            Start round {event.round_list.length + 1}
          </button>
          {confirmFinish ? (
            <>
              <button
                type="button"
                disabled={busy}
                className={buttonClass("quiet", "h-12")}
                onClick={() => void act(() => apiPost<CrewEvent>(user, `${base}/finish`, {}))}
              >
                Yes, finish
              </button>
              <button
                type="button"
                className="min-h-11 px-2 text-body font-bold text-muted"
                onClick={() => {
                  setConfirmFinish(false);
                }}
              >
                Keep playing
              </button>
            </>
          ) : (
            <button
              type="button"
              className={buttonClass("quiet", "h-12")}
              onClick={() => {
                setConfirmFinish(true);
              }}
            >
              Finish event
            </button>
          )}
        </div>
      )}
      {event.can_manage && live && !event.can_start_round && (
        <p className="text-small text-muted">Score or skip every court to start the next round.</p>
      )}
      <p role="alert" className="text-body text-warn empty:hidden">
        {problem}
      </p>

      {!live && (
        <div className="flex flex-col gap-2 rounded-2xl bg-chip p-4">
          <p className="text-body font-bold">That&apos;s a wrap. Every game is on the crew&apos;s record.</p>
          <Link href="/crew" className="self-start text-body font-bold text-primary">
            See the recap on Crew →
          </Link>
        </div>
      )}

      <Results event={event} names={names} />

      {rounds.map((round, i) => (
        <RoundCard
          key={round.number}
          round={round}
          current={i === 0}
          names={names}
          rules={rules}
          bestOf={event.best_of}
          canManage={event.can_manage}
          live={live}
          base={base}
          onChange={onChange}
        />
      ))}

      {event.can_manage && live && <People groupId={groupId} event={event} base={base} onChange={onChange} />}
    </>
  );
}

function Results({ event, names }: { event: CrewEvent; names: ReadonlyMap<string, string> }) {
  if (event.standings) {
    if (event.standings.length === 0) {
      return null;
    }
    return (
      <section aria-labelledby="standings-heading" className="flex flex-col gap-2">
        <h2 id="standings-heading" className="text-title-sm font-bold text-ink">
          Standings, this event only
        </h2>
        <div className="overflow-x-auto rounded-3xl border border-transparent bg-surface shadow-card">
          <table className="w-full text-left text-small tabular-nums">
            <thead>
              <tr className="border-b border-line text-muted">
                <th scope="col" className="px-3 py-2 pl-4 font-bold">
                  Player
                </th>
                <th scope="col" className="px-3 py-2 font-bold">
                  Wins
                </th>
                <th scope="col" className="px-3 py-2 font-bold">
                  Games
                </th>
                <th scope="col" className="px-3 py-2 font-bold">
                  Points
                </th>
              </tr>
            </thead>
            <tbody>
              {event.standings.map((s) => (
                <tr key={s.player_id} className="border-b border-line last:border-b-0">
                  <td className="px-3 py-2 pl-4 font-bold">{names.get(s.player_id) ?? "Someone"}</td>
                  <td className="px-3 py-2">{s.wins}</td>
                  <td className="px-3 py-2">{s.games}</td>
                  <td className="px-3 py-2">{pointDifference(s)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    );
  }
  if (event.mine && event.mine.games > 0) {
    return <p className="rounded-2xl bg-chip px-4 py-3 text-body">{myResultsLine(event.mine)}</p>;
  }
  return null;
}

function RoundCard({
  round,
  current,
  names,
  rules,
  bestOf,
  canManage,
  live,
  base,
  onChange,
}: {
  round: EventRound;
  current: boolean;
  names: ReadonlyMap<string, string>;
  rules: GameRules;
  bestOf: CrewEvent["best_of"];
  canManage: boolean;
  live: boolean;
  base: `/v1/${string}`;
  onChange: (event: CrewEvent) => void;
}) {
  const body = (
    <div className="flex flex-col gap-3">
      <ul className="grid gap-3 sm:grid-cols-2">
        {round.courts.map((court) => (
          <li key={court.court}>
            <CourtCard
              court={court}
              round={round.number}
              names={names}
              rules={rules}
              bestOf={bestOf}
              canManage={canManage}
              live={live}
              base={base}
              onChange={onChange}
            />
          </li>
        ))}
      </ul>
      {round.sitting_out.length > 0 && (
        <p className="text-small text-muted">
          Sitting out: {round.sitting_out.map((id) => names.get(id) ?? "Someone").join(", ")}
        </p>
      )}
    </div>
  );
  if (current) {
    return (
      <section aria-label={`Round ${String(round.number)}`} className="flex flex-col gap-2">
        <h2 className="text-title-sm font-extrabold font-display">Round {round.number}</h2>
        {body}
      </section>
    );
  }
  return (
    <details className="rounded-3xl border border-transparent bg-surface shadow-card p-4">
      <summary className="cursor-pointer text-body font-bold">Round {round.number}</summary>
      <div className="mt-3">{body}</div>
    </details>
  );
}

function CourtCard({
  court,
  round,
  names,
  rules,
  bestOf,
  canManage,
  live,
  base,
  onChange,
}: {
  court: EventCourt;
  round: number;
  names: ReadonlyMap<string, string>;
  rules: GameRules;
  bestOf: CrewEvent["best_of"];
  canManage: boolean;
  live: boolean;
  base: `/v1/${string}`;
  onChange: (event: CrewEvent) => void;
}) {
  const { user } = useSignedIn();
  const [editing, setEditing] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const teamA = teamLine(court.team_a, names);
  const teamB = teamLine(court.team_b, names);
  const scored = court.match_id !== null;
  const open = !scored && !court.skipped && live;
  const label = `Court ${String(court.court)}`;

  async function skip() {
    setProblem(null);
    try {
      onChange(await apiPost<CrewEvent>(user, `${base}/courts/skip`, { round, court: court.court }));
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "That didn't go through just now.");
    }
  }

  return (
    <article
      aria-label={label}
      className="flex flex-col gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-4"
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-title-sm font-bold text-ink">{label}</h3>
        {court.skipped && <span className="text-meta font-bold text-muted">Skipped</span>}
      </div>
      <p className="flex flex-col gap-1 text-body">
        <span className={court.winner === "A" ? "font-extrabold text-win" : "font-bold"}>{teamA}</span>
        <span className="text-meta text-muted">vs</span>
        <span className={court.winner === "B" ? "font-extrabold text-win" : "font-bold"}>{teamB}</span>
      </p>
      {scored && !editing && (
        <div className="flex items-center justify-between gap-2">
          <p className="text-title-sm font-extrabold tabular-nums font-numeral">{scoreText(court.games)}</p>
          {canManage && (
            <button
              type="button"
              className="min-h-11 px-2 text-body font-bold text-primary"
              onClick={() => {
                setEditing(true);
              }}
            >
              Change
            </button>
          )}
        </div>
      )}
      {(open || editing || (court.skipped && canManage && live)) && (
        <ScoreEntry
          label={label}
          teamA={teamA}
          teamB={teamB}
          rules={rules}
          bestOf={bestOf}
          initial={editing ? court.games : []}
          path={`${base}/courts`}
          where={{ round, court: court.court }}
          onSaved={(event) => {
            setEditing(false);
            onChange(event);
          }}
          onCancel={
            editing
              ? () => {
                  setEditing(false);
                }
              : undefined
          }
        />
      )}
      {open && canManage && (
        <button type="button" className="self-start text-small font-bold text-muted" onClick={() => void skip()}>
          Couldn&apos;t finish? Skip this court
        </button>
      )}
      <p role="alert" className="text-small text-warn empty:hidden">
        {problem}
      </p>
    </article>
  );
}

function parseScore(value: string): number | null {
  return /^\d{1,2}$/.test(value) ? Number(value) : null;
}

function ScoreEntry({
  label,
  teamA,
  teamB,
  rules,
  bestOf,
  initial,
  path,
  where,
  onSaved,
  onCancel,
}: {
  label: string;
  teamA: string;
  teamB: string;
  rules: GameRules;
  bestOf: CrewEvent["best_of"];
  initial: readonly { team_a: number; team_b: number }[];
  path: `/v1/${string}`;
  // Which court: sent in the body (the proxy keeps paths short).
  where: { round: number; court: number };
  onSaved: (event: CrewEvent) => void;
  onCancel?: () => void;
}) {
  const { user } = useSignedIn();
  const [scores, setScores] = useState<[string, string][]>(() =>
    Array.from({ length: bestOf }, (_, i) => {
      const g = initial[i];
      return g ? [String(g.team_a), String(g.team_b)] : ["", ""];
    }),
  );
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const parsed = scores.map(([a, b]) => [parseScore(a), parseScore(b)] as const);
  const filled = parsed.flatMap(([a, b]) => (a !== null && b !== null ? [[a, b] as const] : []));
  const shown = gamesToShow(bestOf, rules, filled);
  const entered = parsed.slice(0, shown);
  const complete = entered.every(([a, b]) => a !== null && b !== null);
  const games = complete ? entered.map(([a, b]) => [a ?? 0, b ?? 0] as const) : [];
  const check = complete ? validateMatch(rules, bestOf, games) : null;
  const side = (team: Team) => (team === "A" ? teamA : teamB);

  async function save() {
    if (!check?.ok) {
      return;
    }
    setSaving(true);
    setProblem(null);
    try {
      onSaved(
        await apiPut<CrewEvent>(user, path, {
          ...where,
          games: games.map(([a, b]) => ({ team_a: a, team_b: b })),
        }),
      );
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "That didn't save just now.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
    >
      {scores.slice(0, shown).map(([a, b], game) => (
        <div key={game} className="grid grid-cols-[3.5rem_1fr_1fr] items-center gap-2">
          <span className="text-small font-bold text-muted">Game {game + 1}</span>
          {([a, b] as const).map((value, i) => (
            <input
              key={i}
              value={value}
              onChange={(event) => {
                const next = scores.map((pair) => [...pair] as [string, string]);
                const row = next[game];
                if (row) {
                  row[i] = event.target.value;
                }
                setScores(next);
              }}
              inputMode="numeric"
              pattern="[0-9]*"
              autoComplete="off"
              maxLength={2}
              aria-label={`${label}, game ${String(game + 1)}, ${i === 0 ? teamA : teamB}`}
              className="h-12 w-full rounded-xl border border-line bg-bg text-center text-title-sm font-extrabold text-ink font-numeral"
            />
          ))}
        </div>
      ))}
      <p aria-live="polite" className="min-h-5 text-small font-bold">
        {check?.ok && <span className="text-win">✓ {side(check.value)} win.</span>}
        {check && !check.ok && <span className="text-warn">{check.problem}</span>}
      </p>
      <div className="flex items-center gap-2">
        <button type="submit" disabled={!check?.ok || saving} className={buttonClass("primary", "min-h-11")}>
          {saving ? "Saving…" : "Save score"}
        </button>
        {onCancel && (
          <button type="button" className="min-h-11 px-2 text-body font-bold text-muted" onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
      <p role="alert" className="text-small text-warn empty:hidden">
        {problem}
      </p>
    </form>
  );
}

function People({
  groupId,
  event,
  base,
  onChange,
}: {
  groupId: string;
  event: CrewEvent;
  base: `/v1/${string}`;
  onChange: (event: CrewEvent) => void;
}) {
  const { user } = useSignedIn();
  const players = useApiGet<Player[]>(`/v1/groups/${groupId}/players`);
  const [adding, setAdding] = useState("");
  const [problem, setProblem] = useState<string | null>(null);
  const here = event.people.filter((p) => p.here);
  const hereIds = new Set(here.map((p) => p.player_id));
  const addable = players.result.kind === "ready" ? players.result.data.filter((p) => !hereIds.has(p.id)) : [];

  async function change(call: () => Promise<void>) {
    setProblem(null);
    try {
      await call();
      onChange(await apiGet<CrewEvent>(user, base));
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "That didn't go through just now.");
    }
  }

  return (
    // Folded away: on a phone the courts come first; this is for arrivals and leavers.
    <details className="rounded-3xl border border-transparent bg-surface shadow-card p-4">
      <summary className="min-h-11 cursor-pointer content-center text-body font-bold">
        Who&apos;s playing ({here.length})
      </summary>
      <section aria-label="Playing" className="mt-2 flex flex-col gap-2">
        <p className="text-small text-muted">Arrivals and leavers count from the next round.</p>
        <ul className="flex flex-col divide-y divide-line rounded-3xl border border-transparent bg-surface shadow-card">
          {here.map((p) => (
            <li key={p.player_id} className="flex items-center justify-between gap-3 px-4 py-2">
              <span className="font-bold">{p.display_name}</span>
              <button
                type="button"
                className="min-h-11 px-2 text-small font-bold text-muted"
                aria-label={`${p.display_name} is leaving`}
                onClick={() => void change(() => apiPost<undefined>(user, `${base}/players/${p.player_id}/leave`, {}))}
              >
                Leaving
              </button>
            </li>
          ))}
        </ul>
        {addable.length > 0 && here.length < MAX_PLAYERS && (
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (adding) {
                void change(async () => {
                  await apiPost<undefined>(user, `${base}/players`, { player_id: adding });
                  setAdding("");
                });
              }
            }}
          >
            <select
              aria-label="Someone arriving"
              value={adding}
              onChange={(e) => {
                setAdding(e.target.value);
              }}
              className="min-h-11 grow rounded-xl border border-line bg-surface px-3 text-field"
            >
              <option value="">Someone arriving…</option>
              {addable.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.display_name}
                </option>
              ))}
            </select>
            <button type="submit" disabled={!adding} className={buttonClass("quiet", "min-h-11")}>
              Add
            </button>
          </form>
        )}
        {here.length < MAX_PLAYERS && (
          <AddGuestInline
            groupId={groupId}
            label="Someone new? Add them as a guest"
            onAdded={async (guest) => {
              await change(() => apiPost<undefined>(user, `${base}/players`, { player_id: guest.id }));
              players.reload();
            }}
          />
        )}
        <p role="alert" className="text-small text-warn empty:hidden">
          {problem}
        </p>
      </section>
    </details>
  );
}
