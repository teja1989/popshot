"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useMemo, useRef, useState, type SubmitEvent } from "react";

import { apiPost, ApiError } from "@/lib/api-client";
import { teamNames, toLocalInput, type LogGameBody, type Match, type Player } from "@/lib/games";
import type { Format, GroupDetail } from "@/lib/groups";
import { gamesToShow, validateMatch, type BestOf, type PointsTo, type Team } from "@/lib/scoring";

import { useSignedIn } from "./auth";
import { PlayerPicker } from "./player-picker";
import { useApiGet } from "./use-api";
import { rememberGroup } from "./use-current-group";
import { buttonClass } from "./ui/button";
import { BackIcon } from "./ui/icons";
import { segmentOption, segmentTrack } from "./ui/segmented";

const TEAM_SIZE: Record<Format, number> = { doubles: 2, singles: 1 };
const TEAMS: Team[] = ["A", "B"];

export function LogGameView({ groupId }: { groupId: string }) {
  const group = useApiGet<GroupDetail>(`/v1/groups/${groupId}`);
  const roster = useApiGet<Player[]>(`/v1/groups/${groupId}/players`);

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-5 px-5 pt-6 pb-12 lg:max-w-xl lg:px-8 lg:pt-10">
      <Link
        href={`/groups/${groupId}`}
        className="-ml-1 flex min-h-11 items-center gap-1.5 self-start text-[15px] font-bold text-primary no-underline"
      >
        <BackIcon />
        {group.result.kind === "ready" ? group.result.data.name : "Back to the group"}
      </Link>
      <h1 className="text-[32px] leading-tight font-extrabold tracking-[-0.02em] [font-stretch:110%]">Log a game</h1>

      {(group.result.kind === "loading" || roster.result.kind === "loading") && <p className="text-muted">Loading…</p>}

      {(group.result.kind === "error" || roster.result.kind === "error") && (
        <section role="alert" className="flex flex-col items-start gap-3 rounded-2xl border border-line bg-surface p-5">
          {group.result.kind === "error" && group.result.status === 404 ? (
            <p>We couldn&apos;t find that group. You can only log games in groups you&apos;re in.</p>
          ) : (
            <>
              <p>We couldn&apos;t load the group just now.</p>
              <button
                type="button"
                className={buttonClass("quiet")}
                onClick={() => {
                  group.reload();
                  roster.reload();
                }}
              >
                Try again
              </button>
            </>
          )}
        </section>
      )}

      {group.result.kind === "ready" && roster.result.kind === "ready" && (
        <LogGameForm
          group={group.result.data}
          players={roster.result.data}
          onGuestAdded={(guest) => {
            if (roster.result.kind === "ready") {
              roster.replace([...roster.result.data, guest]);
            }
          }}
        />
      )}
    </main>
  );
}

type Scores = [string, string][];

function parseScore(value: string): number | null {
  return /^\d{1,2}$/.test(value) ? Number(value) : null;
}

function LogGameForm({
  group,
  players,
  onGuestAdded,
}: {
  group: GroupDetail;
  players: Player[];
  onGuestAdded: (guest: Player) => void;
}) {
  const { user } = useSignedIn();
  const router = useRouter();
  const ids = useId();
  const me = players.find((p) => p.is_me);
  const [format, setFormat] = useState<Format>(group.default_format);
  const [pointsTo, setPointsTo] = useState<PointsTo>(group.default_points_to);
  const [winByTwo, setWinByTwo] = useState(group.default_win_by_two);
  const [bestOf, setBestOf] = useState<BestOf>(1);
  // You're on team A to start with; take yourself out if you're only keeping score.
  const [teams, setTeams] = useState<Record<Team, (string | null)[]>>(() => ({
    A: [me?.id ?? null, null].slice(0, TEAM_SIZE[group.default_format]),
    B: [null, null].slice(0, TEAM_SIZE[group.default_format]),
  }));
  const [scores, setScores] = useState<Scores>([
    ["", ""],
    ["", ""],
    ["", ""],
  ]);
  const [earlier, setEarlier] = useState(false);
  const [playedAt, setPlayedAt] = useState(() => toLocalInput(new Date()));
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const problemRef = useRef<HTMLParagraphElement>(null);

  const byId = useMemo(() => new Map(players.map((p) => [p.id, p])), [players]);
  const rules = { pointsTo, winByTwo };
  const parsed = scores.map(([a, b]) => [parseScore(a), parseScore(b)] as const);
  const shown = gamesToShow(
    bestOf,
    rules,
    parsed.flatMap(([a, b]) => (a !== null && b !== null ? [[a, b] as const] : [])),
  );
  const entered = parsed.slice(0, shown);
  const complete = entered.every(([a, b]) => a !== null && b !== null);
  const games = complete ? entered.map(([a, b]) => [a ?? 0, b ?? 0] as const) : [];
  const check = complete ? validateMatch(rules, bestOf, games) : null;
  const chosen = [...teams.A, ...teams.B];
  const teamsReady = chosen.every((id) => id !== null);
  const label = (team: Team) => {
    const names = teams[team].flatMap((id) => (id ? [byId.get(id)?.display_name ?? "?"] : []));
    return names.length === TEAM_SIZE[format] ? teamNames(names) : `Team ${team}`;
  };

  function changeFormat(next: Format) {
    setFormat(next);
    setTeams((current) => ({
      A: [current.A[0] ?? null, current.A[1] ?? null].slice(0, TEAM_SIZE[next]),
      B: [current.B[0] ?? null, current.B[1] ?? null].slice(0, TEAM_SIZE[next]),
    }));
  }

  function pick(team: Team, slot: number, playerId: string | null) {
    setTeams((current) => {
      const next = { A: [...current.A], B: [...current.B] };
      next[team][slot] = playerId;
      return next;
    });
  }

  function setScore(game: number, side: 0 | 1, value: string) {
    setScores((current) => {
      const digits = value.replace(/\D/g, "").slice(0, 2);
      return current.map((row, index) => {
        if (index !== game) {
          return row;
        }
        return side === 0 ? [digits, row[1]] : [row[0], digits];
      });
    });
  }

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!teamsReady) {
      setProblem(format === "doubles" ? "Pick two players for each team." : "Pick a player for each side.");
      problemRef.current?.focus();
      return;
    }
    if (!check?.ok) {
      setProblem(check ? check.problem : "Enter the score for each game.");
      problemRef.current?.focus();
      return;
    }
    const body: LogGameBody = {
      format,
      points_to: pointsTo,
      win_by_two: winByTwo,
      best_of: bestOf,
      team_a: teams.A.filter((id): id is string => id !== null),
      team_b: teams.B.filter((id): id is string => id !== null),
      games: games.map(([a, b]) => ({ team_a: a, team_b: b })),
    };
    if (earlier) {
      const when = new Date(playedAt);
      if (Number.isNaN(when.getTime())) {
        setProblem("Pick when it was played.");
        problemRef.current?.focus();
        return;
      }
      body.played_at = when.toISOString();
    }
    setSaving(true);
    setProblem(null);
    try {
      await apiPost<Match>(user, `/v1/groups/${group.id}/matches`, body);
      rememberGroup(group.id);
      router.push("/games?logged=1");
    } catch (error) {
      setProblem(
        error instanceof ApiError && error.detail
          ? error.detail
          : "We couldn't log the game just now. Your entries are still here; try again in a moment.",
      );
      problemRef.current?.focus();
      setSaving(false);
    }
  }

  return (
    <form className="flex animate-rise flex-col gap-6" onSubmit={(event) => void submit(event)} noValidate>
      <section className="flex flex-col gap-4 rounded-2xl border border-line bg-surface p-5">
        <div className="grid gap-4 sm:grid-cols-2 sm:gap-3">
          <fieldset>
            <legend className="mb-2 text-[15px] font-bold">Format</legend>
            <div className={`${segmentTrack} grid-cols-2`}>
              {(["doubles", "singles"] as const).map((value) => (
                <label key={value} className={segmentOption}>
                  <input
                    type="radio"
                    name="format"
                    checked={format === value}
                    onChange={() => {
                      changeFormat(value);
                    }}
                    className="sr-only"
                  />
                  {value === "doubles" ? "Doubles" : "Singles"}
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend className="mb-2 text-[15px] font-bold">Match</legend>
            <div className={`${segmentTrack} grid-cols-2`}>
              {([1, 3] as const).map((value) => (
                <label key={value} className={segmentOption}>
                  <input
                    type="radio"
                    name="best_of"
                    checked={bestOf === value}
                    onChange={() => {
                      setBestOf(value);
                    }}
                    className="sr-only"
                  />
                  {value === 1 ? "1 game" : "Best of 3"}
                </label>
              ))}
            </div>
          </fieldset>
        </div>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <fieldset>
            <legend className="mb-2 text-[15px] font-bold">Games to</legend>
            <div className={`${segmentTrack} grid-cols-3`}>
              {([11, 15, 21] as const).map((value) => (
                <label key={value} className={`${segmentOption} w-12`}>
                  <input
                    type="radio"
                    name="points_to"
                    checked={pointsTo === value}
                    onChange={() => {
                      setPointsTo(value);
                    }}
                    className="sr-only"
                  />
                  {value}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="flex min-h-11 cursor-pointer items-center gap-3 text-[15px] font-bold">
            <input
              type="checkbox"
              role="switch"
              checked={winByTwo}
              onChange={(event) => {
                setWinByTwo(event.target.checked);
              }}
              className="relative h-[26px] w-11 cursor-pointer appearance-none rounded-full bg-line transition-colors duration-200 before:absolute before:top-[3px] before:left-[3px] before:size-5 before:rounded-full before:bg-surface before:shadow-sm before:transition-transform before:duration-200 before:ease-court checked:bg-primary checked:before:translate-x-[18px]"
            />
            Win by 2
          </label>
        </div>
      </section>

      <section aria-labelledby={`${ids}-teams`} className="flex flex-col gap-3">
        <h2 id={`${ids}-teams`} className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
          Who played
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {TEAMS.map((team) => (
            <fieldset key={team} className="flex flex-col gap-2 rounded-2xl border border-line bg-surface p-4">
              <legend className="sr-only">Team {team}</legend>
              <p aria-hidden="true" className="text-[13px] font-bold tracking-[0.08em] text-muted uppercase">
                Team {team}
              </p>
              {teams[team].map((playerId, slot) => (
                <PlayerPicker
                  key={`${team}-${String(slot)}`}
                  groupId={group.id}
                  label={`Team ${team}, player ${String(slot + 1)}`}
                  players={players}
                  selected={playerId ? (byId.get(playerId) ?? null) : null}
                  taken={new Set(chosen.filter((id): id is string => id !== null && id !== playerId))}
                  onPick={(id) => {
                    pick(team, slot, id);
                  }}
                  onGuestAdded={onGuestAdded}
                />
              ))}
            </fieldset>
          ))}
        </div>
      </section>

      <section aria-labelledby={`${ids}-score`} className="flex flex-col gap-3">
        <h2 id={`${ids}-score`} className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
          Score
        </h2>
        <div className="flex flex-col gap-2 rounded-2xl border border-line bg-surface p-4">
          <div className="grid grid-cols-[4.5rem_1fr_1fr] items-end gap-3 text-[13px] font-bold text-muted">
            <span />
            <span className="truncate">{label("A")}</span>
            <span className="truncate">{label("B")}</span>
          </div>
          {scores.slice(0, shown).map(([a, b], game) => (
            <div key={game} className="grid grid-cols-[4.5rem_1fr_1fr] items-center gap-3">
              <span className="text-[15px] font-bold">Game {game + 1}</span>
              {([a, b] as const).map((value, side) => (
                <input
                  key={side}
                  value={value}
                  onChange={(event) => {
                    setScore(game, side === 0 ? 0 : 1, event.target.value);
                  }}
                  inputMode="numeric"
                  pattern="[0-9]*"
                  autoComplete="off"
                  maxLength={2}
                  aria-label={`Game ${String(game + 1)}, ${label(side === 0 ? "A" : "B")}`}
                  className="h-14 w-full rounded-xl border border-line bg-bg text-center text-[28px] font-extrabold text-ink [font-stretch:75%]"
                />
              ))}
            </div>
          ))}
          <p aria-live="polite" className="min-h-6 pt-1 text-[15px] font-bold">
            {check?.ok && teamsReady && (
              <span className="text-win">
                ✓ {label(check.value)} {format === "singles" ? "wins" : "win"} {games.map(([x, y]) => (check.value === "A" ? `${String(x)}–${String(y)}` : `${String(y)}–${String(x)}`)).join(", ")}.
              </span>
            )}
            {check && !check.ok && <span className="text-warn">{check.problem}</span>}
          </p>
        </div>
      </section>

      <fieldset className="flex flex-col gap-3">
        <legend className="mb-3 text-xs font-bold tracking-[0.1em] text-muted uppercase">When</legend>
        <div className={`${segmentTrack} grid-cols-2`}>
          {[false, true].map((value) => (
            <label key={String(value)} className={segmentOption}>
              <input
                type="radio"
                name="when"
                checked={earlier === value}
                onChange={() => {
                  setEarlier(value);
                }}
                className="sr-only"
              />
              {value ? "Earlier" : "Just now"}
            </label>
          ))}
        </div>
        {earlier && (
          <label className="flex flex-col gap-2">
            <span className="text-[15px] font-bold">Played at</span>
            <input
              type="datetime-local"
              value={playedAt}
              max={toLocalInput(new Date())}
              onChange={(event) => {
                setPlayedAt(event.target.value);
              }}
              className="min-h-12 rounded-xl border border-line bg-bg px-4 text-[17px] text-ink"
            />
            <span className="text-[14px] text-muted">Games can be logged up to 30 days later.</span>
          </label>
        )}
      </fieldset>

      <p ref={problemRef} tabIndex={-1} role="alert" className="text-[15px] font-bold text-warn empty:hidden">
        {problem}
      </p>
      <button type="submit" className={buttonClass("action", "h-14 w-full")} disabled={saving}>
        {saving ? "Logging…" : "Log game"}
      </button>
      <p className="-mt-3 text-center text-[14px] text-muted">
        Someone on the other team confirms it. Until then it shows as waiting.
      </p>
    </form>
  );
}
