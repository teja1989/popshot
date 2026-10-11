"use client";

import Link from "next/link";
import { useState } from "react";

import { apiPut, ApiError } from "@/lib/api-client";
import { DEFAULT_START, LEVELS, levelLabel, points, type Level, type MyRating } from "@/lib/board";

import { useAuth, useSignedIn } from "./auth";
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
      <h2 id="points-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
        Crew points
      </h2>
      <div className="flex flex-col gap-4 rounded-2xl border border-line bg-surface p-5">
        {ratings.result.kind === "ready" && ratings.result.data.length === 0 && (
          <p className="text-muted">Your crew points show up after your first game.</p>
        )}
        {ratings.result.kind === "ready" && ratings.result.data.length > 0 && (
          <ul className="flex flex-col gap-3">
            {ratings.result.data.map((r) => (
              <li key={r.group_id} className="flex items-center justify-between gap-3">
                <span className="flex min-w-0 flex-col">
                  <Link href={`/groups/${r.group_id}`} className="truncate font-bold text-ink no-underline">
                    {r.group_name}
                  </Link>
                  <span className="text-[14px] text-muted">
                    {r.rank !== null
                      ? `#${String(r.rank)} of ${String(r.ranked_of)} · ${String(r.matches)} games`
                      : `${String(r.matches)} of ${String(r.matches + r.to_go)} games to be ranked`}
                  </span>
                </span>
                <span className="text-[28px] leading-none font-extrabold tabular-nums [font-stretch:75%]">{points(r.rating)}</span>
              </li>
            ))}
          </ul>
        )}
        {level && ratings.result.kind === "ready" && ratings.result.data[0] && (
          <p className="rounded-xl bg-chip px-3 py-2 text-[15px]">
            You said {levelLabel(level)} ({points(start)}); your games say {points(ratings.result.data[0].rating)}.
          </p>
        )}

        <fieldset className="flex flex-col gap-2 border-t border-line pt-4">
          <legend className="mb-1 text-[16px] font-extrabold">Your level</legend>
          <p className="-mt-1 mb-1 text-[14px] text-muted">
            Optional. It&apos;s where your crew points start; your games take over within about 10.
          </p>
          {[{ value: null, label: "Not set", start: DEFAULT_START, hint: "Start at the middle" }, ...LEVELS].map((option) => (
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
                <span className="text-[13px] text-muted">{option.hint}</span>
              </span>
              <span className="text-[14px] font-bold text-muted tabular-nums">{points(option.start)}</span>
            </label>
          ))}
        </fieldset>
        <p role="alert" className="text-[15px] text-warn empty:hidden">
          {problem}
        </p>
      </div>
    </section>
  );
}
