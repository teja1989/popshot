"use client";

import Link from "next/link";
import { useState } from "react";

import { apiPut, ApiError } from "@/lib/api-client";
import {
  change,
  DEFAULT_START,
  edgeText,
  LEVELS,
  levelLabel,
  points,
  TREND_LABEL,
  trendSummary,
  type Level,
  type MyRating,
} from "@/lib/board";

import { useAuth, useSignedIn } from "./auth";
import { CrewPointsInfo } from "./crew-points-info";
import { useApiGet } from "./use-api";

/** Your crew points in each group, and the self-rated level they started from. */
export function CrewPointsSection() {
  const { me, user } = useSignedIn();
  const { updateMe } = useAuth();
  const ratings = useApiGet<MyRating[]>("/v1/me/ratings");
  const [problem, setProblem] = useState<string | null>(null);
  // Your saved level, unless you've just picked one: shown straight away, undone if saving fails.
  const [picked, setPicked] = useState<Level | null | undefined>(undefined);
  const level = picked !== undefined ? picked : ((me?.self_level ?? null) as Level | null);
  const start = LEVELS.find((l) => l.value === level)?.start ?? DEFAULT_START;

  async function choose(next: Level | null) {
    const before = picked;
    setPicked(next);
    setProblem(null);
    try {
      await apiPut(user, "/v1/me/level", { level: next });
      if (me) {
        updateMe({ ...me, self_level: next });
      }
      ratings.reload();
    } catch (error) {
      setPicked(before);
      setProblem(error instanceof ApiError && error.detail ? error.detail : "We couldn't save that just now.");
    }
  }

  return (
    <section aria-labelledby="points-heading" className="flex animate-rise flex-col gap-3 [animation-delay:30ms]">
      <div className="-my-2 flex items-center gap-0.5">
        <h2 id="points-heading" className="text-title-sm font-bold text-ink">
          Crew points
        </h2>
        <CrewPointsInfo />
      </div>
      <div className="flex flex-col gap-4 rounded-3xl border border-transparent bg-surface shadow-card p-5">
        {ratings.result.kind === "ready" && ratings.result.data.length === 0 && (
          <p className="text-muted">Your crew points show up after your first game.</p>
        )}
        {ratings.result.kind === "ready" && ratings.result.data.length > 0 && (
          <>
            {trendSummary(ratings.result.data) && (
              <p className="rounded-xl bg-chip px-3 py-2 text-body font-bold">{trendSummary(ratings.result.data)}</p>
            )}
            <ul className="flex flex-col gap-4">
              {ratings.result.data.map((r) => (
                <li key={r.group_id} className="flex flex-col gap-1">
                  <span className="flex items-center justify-between gap-3">
                    <span className="flex min-w-0 flex-col">
                      <Link href={`/groups/${r.group_id}`} className="truncate font-bold text-ink no-underline">
                        {r.group_name}
                      </Link>
                      <span className="text-small text-muted">
                        {r.to_go > 0
                          ? `${String(r.matches)} games · settling, ${String(r.to_go)} to go`
                          : `${String(r.matches)} games`}
                      </span>
                    </span>
                    <span className="text-title-lg leading-none font-extrabold tabular-nums font-numeral">
                      {points(r.rating)}
                    </span>
                  </span>
                  <MonthLine rating={r} />
                </li>
              ))}
            </ul>
          </>
        )}
        {level && ratings.result.kind === "ready" && ratings.result.data[0] && (
          <p className="rounded-xl bg-chip px-3 py-2 text-body">
            You said {levelLabel(level)} ({points(start)}); your games say {points(ratings.result.data[0].rating)}.
          </p>
        )}

        <fieldset className="flex flex-col gap-2 border-t border-line pt-4">
          <legend className="mb-1 text-lead font-extrabold">Your level</legend>
          <p className="-mt-1 mb-1 text-small text-muted">
            Optional. It&apos;s where your crew points start; your games take over within about 10.
          </p>
          {[{ value: null, label: "Not set", start: DEFAULT_START, hint: "Start at the middle" }, ...LEVELS].map(
            (option) => (
              <label
                key={option.label}
                className="flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border border-line bg-bg px-4 has-[:checked]:border-primary has-[:checked]:bg-chip"
              >
                <input
                  type="radio"
                  name="self_level"
                  checked={level === option.value}
                  onChange={() => void choose(option.value)}
                  className="size-4 accent-primary"
                />
                <span className="flex grow flex-col">
                  <span className="font-bold">{option.label}</span>
                  <span className="text-meta text-muted">{option.hint}</span>
                </span>
                <span className="text-small font-bold text-muted tabular-nums">{points(option.start)}</span>
              </label>
            ),
          )}
        </fieldset>
        <p role="alert" className="text-body text-warn empty:hidden">
          {problem}
        </p>
      </div>
    </section>
  );
}

/** How the last 30 days have gone in one crew. */
function MonthLine({ rating: r }: { rating: MyRating }) {
  if (r.month_games === 0) {
    return <p className="text-small text-muted">No games in the last 30 days.</p>;
  }
  const moved = change(r.month_change);
  const games = `${String(r.month_games)} game${r.month_games === 1 ? "" : "s"}`;
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-small text-muted">
      {r.trend && (
        <span
          className={`rounded-full px-2 py-0.5 text-meta font-bold ${
            r.trend === "climbing"
              ? "bg-win text-on-win"
              : r.trend === "slipping"
                ? "bg-chip text-ink"
                : "border border-line text-ink"
          }`}
        >
          {TREND_LABEL[r.trend]}
        </span>
      )}
      <span>
        {moved ? <span className={`font-bold ${moved.up ? "text-win" : "text-loss"}`}>{moved.text}</span> : "No change"}{" "}
        in 30 days · {games}
        {r.trend && r.month_edge !== null ? ` · ${edgeText(r.month_edge)}` : " · a few more for a trend"}
      </span>
    </p>
  );
}
