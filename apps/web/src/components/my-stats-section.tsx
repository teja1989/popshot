"use client";

import { useState } from "react";

import { change, points } from "@/lib/board";
import { playedWhen, teamNames } from "@/lib/games";
import type { GroupSummary } from "@/lib/groups";
import {
  busiestDay,
  linePoints,
  record,
  statsPath,
  streakText,
  weeklyCounts,
  WINDOWS,
  type MyStats,
  type RecordOut,
  type Window,
} from "@/lib/stats";

import { GroupSwitcher } from "./group-switcher";
import { useApiGet } from "./use-api";
import { useCurrentGroup } from "./use-current-group";
import { segmentOption, segmentTrack } from "./ui/segmented";

const H2H_SHOWN = 5;

/** Your dashboard: crew points over time, stats and activity, one group and window at a time. */
export function MyStatsSection() {
  const { result } = useApiGet<GroupSummary[]>("/v1/groups");
  const groups = result.kind === "ready" ? result.data.filter((g) => g.my_status === "active") : [];
  const { current, choose } = useCurrentGroup(groups);
  const [days, setDays] = useState<Window>(30);
  if (!current) {
    return null;
  }

  return (
    <section aria-labelledby="stats-heading" className="flex animate-rise flex-col gap-3 [animation-delay:45ms]">
      <h2 id="stats-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
        Your stats
      </h2>
      {groups.length > 1 && <GroupSwitcher groups={groups} current={current} onChange={choose} />}
      <fieldset>
        <legend className="sr-only">Show stats from</legend>
        <div className={`${segmentTrack} grid-cols-3`}>
          {WINDOWS.map((w) => (
            <label key={w.label} className={segmentOption}>
              <input
                type="radio"
                name="stats-window"
                checked={days === w.value}
                onChange={() => {
                  setDays(w.value);
                }}
                className="sr-only"
              />
              {w.label}
            </label>
          ))}
        </div>
      </fieldset>
      <GroupStats key={current.id} group={current} days={days} />
    </section>
  );
}

function GroupStats({ group, days }: { group: GroupSummary; days: Window }) {
  const { result, reload } = useApiGet<MyStats>(statsPath(group.id, days));
  if (result.kind === "loading") {
    return <p className="text-muted">Loading your stats…</p>;
  }
  if (result.kind === "error") {
    return (
      <p role="alert" className="text-muted">
        We couldn&apos;t load your stats just now.{" "}
        <button type="button" className="font-bold text-primary underline" onClick={reload}>
          Try again
        </button>
      </p>
    );
  }
  const s = result.data;
  if (s.rating_now === null) {
    return (
      <p className="rounded-2xl border border-line bg-surface p-5 text-muted">
        Your stats in {group.name} show up after your first game.
      </p>
    );
  }
  const windowLabel = WINDOWS.find((w) => w.value === s.days)?.label.toLowerCase() ?? "all time";
  if (s.matches === 0) {
    return (
      <>
        <RatingCard stats={s} />
        <p className="rounded-2xl border border-line bg-surface p-5 text-muted">
          No games in {group.name} in the last {windowLabel}. Try a longer window, or get a game in.
        </p>
      </>
    );
  }
  const streak = streakText(s.current_streak);
  const opponents = s.head_to_head.slice(0, H2H_SHOWN);

  return (
    <>
      <RatingCard stats={s} />
      <div className="flex flex-col gap-4 rounded-2xl border border-line bg-surface p-5">
        <p className="text-[16px]">
          <span className="font-bold">{group.name}</span>
          <span className="text-muted">
            {" "}
            · {s.matches} games · {record(s.wins, s.matches - s.wins)}
            {streak && ` · ${streak}`}
          </span>
        </p>

        <dl className="grid grid-cols-2 gap-2">
          <Tile label="Close games" value={record(s.close_won, s.close_lost)} hint="won–lost" />
          <Tile label="Skunks" value={record(s.skunks_given, s.skunks_taken)} hint="given–taken" />
          <Tile label="Upset wins" value={String(s.upset_wins)} hint="vs higher-rated teams" />
          <Tile label="Best win streak" value={String(s.longest_win_streak)} hint="wins in a row" />
        </dl>

        <div className="grid gap-2 sm:grid-cols-2">
          <Pairing
            label="Best partner"
            found={s.best_partner}
            describe={(r) => `Won ${String(r.won)} of ${String(r.played)} together, all time`}
            empty={`Shows up once you've played ${String(s.min_pairing)} games with the same partner.`}
          />
          <Pairing
            label="Nemesis"
            found={s.nemesis}
            describe={(r) => `You've won ${String(r.won)} of ${String(r.played)}, all time`}
            empty="Nobody has your number yet."
          />
        </div>

        {s.biggest_upset && (
          <p className="rounded-xl bg-chip px-3 py-2 text-[15px]">
            Your biggest upset: you beat {teamNames(s.biggest_upset.losers.map((p) => p.display_name))} from{" "}
            {points(s.biggest_upset.gap)} points behind ({playedWhen(s.biggest_upset.played_at)}).
          </p>
        )}

        {opponents.length > 0 && (
          <div className="flex flex-col gap-2">
            <h3 className="text-[16px] font-extrabold">Head to head</h3>
            <ul aria-label="Head to head" className="flex flex-col">
              {opponents.map((r) => (
                <li
                  key={r.player.player_id}
                  className="flex items-center justify-between gap-3 border-b border-line py-2 last:border-b-0"
                >
                  <span className="min-w-0 truncate font-bold">
                    {r.player.display_name}
                    {r.player.is_guest && <span className="text-[12px] font-semibold text-muted"> · guest</span>}
                  </span>
                  <span className="text-[15px] text-muted tabular-nums">
                    <span className="font-bold text-ink">{record(r.won, r.played - r.won)}</span> won–lost
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <ActivityCard stats={s} />
    </>
  );
}

function Tile({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="flex flex-col gap-0.5 rounded-xl bg-bg px-3 py-2">
      <dt className="text-[13px] font-bold text-muted">{label}</dt>
      <dd className="text-[24px] leading-none font-extrabold tabular-nums [font-stretch:75%]">{value}</dd>
      <dd className="text-[12px] text-muted">{hint}</dd>
    </div>
  );
}

function Pairing({
  label,
  found,
  describe,
  empty,
}: {
  label: string;
  found: RecordOut | null;
  describe: (r: RecordOut) => string;
  empty: string;
}) {
  return (
    <div className="flex flex-col gap-0.5 rounded-xl border border-line px-3 py-2">
      <span className="text-[13px] font-bold text-muted">{label}</span>
      {found ? (
        <>
          <span className="truncate text-[17px] font-extrabold">{found.player.display_name}</span>
          <span className="text-[14px] text-muted">{describe(found)}</span>
        </>
      ) : (
        <span className="text-[14px] text-muted">{empty}</span>
      )}
    </div>
  );
}

const CHART_W = 320;
const CHART_H = 96;

function RatingCard({ stats }: { stats: MyStats }) {
  const now = stats.rating_now ?? 0;
  const moved = stats.rating_start === null ? null : change(now - stats.rating_start);
  const values = [...(stats.rating_start === null ? [] : [stats.rating_start]), ...stats.timeline.map((p) => p.rating)];
  const pts = linePoints(values, CHART_W, CHART_H, 6);
  const last = pts[pts.length - 1];
  const form = stats.timeline.slice(-10).reverse();
  const low = Math.min(...values);
  const high = Math.max(...values);

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
      <div className="flex items-end justify-between gap-3">
        <span className="flex flex-col">
          <span className="text-[13px] font-bold text-muted">Crew points</span>
          <span className="text-[36px] leading-none font-extrabold tabular-nums [font-stretch:75%]">{points(now)}</span>
        </span>
        {moved && (
          <span className={`text-[15px] font-bold ${moved.up ? "text-win" : "text-loss"}`}>
            {moved.text}
            <span className="font-normal text-muted">
              {stats.days ? ` in ${String(stats.days)} days` : " all time"}
            </span>
          </span>
        )}
      </div>
      {pts.length > 1 && (
        <figure className="flex flex-col gap-1">
          <svg
            viewBox={`0 0 ${String(CHART_W)} ${String(CHART_H)}`}
            className="h-24 w-full"
            role="img"
            aria-label={`Crew points over ${String(stats.timeline.length)} games, from ${points(values[0] ?? now)} to ${points(now)}. Lowest ${points(low)}, highest ${points(high)}.`}
          >
            <polyline
              points={pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ")}
              fill="none"
              strokeWidth="2.5"
              strokeLinejoin="round"
              strokeLinecap="round"
              className="stroke-primary"
            />
            {last && <circle cx={last.x} cy={last.y} r="4.5" className="fill-ball stroke-primary" strokeWidth="2" />}
          </svg>
          <figcaption className="flex justify-between text-[12px] text-muted tabular-nums">
            <span>Low {points(low)}</span>
            <span>High {points(high)}</span>
          </figcaption>
        </figure>
      )}
      {form.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-[13px] text-muted">
          <span>Form</span>
          <span
            className="flex gap-1"
            aria-label={`Last ${String(form.length)}, newest first: ${form.map((p) => (p.won ? "W" : "L")).join(" ")}`}
          >
            {form.map((p, i) => (
              <span
                key={`${p.played_at}-${String(i)}`}
                aria-hidden="true"
                className={
                  p.won
                    ? "flex size-5 items-center justify-center rounded bg-win text-[10px] font-extrabold text-on-win"
                    : "flex size-5 items-center justify-center rounded border border-dashed border-loss text-[10px] font-extrabold text-muted"
                }
              >
                {p.won ? "W" : "L"}
              </span>
            ))}
          </span>
        </div>
      )}
    </div>
  );
}

const BAR_W = 320;
const BAR_H = 64;

function ActivityCard({ stats }: { stats: MyStats }) {
  const weeks = weeklyCounts(stats.timeline, stats.days === 30 || stats.days === 90 ? stats.days : null);
  const most = Math.max(1, ...weeks.map((w) => w.count));
  const slot = BAR_W / weeks.length;
  // Thin bars for a short window, so five weeks don't look like five slabs.
  const barWidth = Math.min(slot * 0.7, 18);
  const doubles = stats.timeline.filter((p) => p.doubles).length;
  const singles = stats.timeline.length - doubles;
  const day = busiestDay(stats.timeline);
  const busiestWeek = Math.max(...weeks.map((w) => w.count));

  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
      <h3 className="text-[16px] font-extrabold">Activity</h3>
      <figure className="flex flex-col gap-1">
        <svg
          viewBox={`0 0 ${String(BAR_W)} ${String(BAR_H)}`}
          className="h-16 w-full"
          role="img"
          aria-label={`Games per week over ${String(weeks.length)} weeks. Most in a week: ${String(busiestWeek)}. This week: ${String(weeks[weeks.length - 1]?.count ?? 0)}.`}
        >
          {weeks.map((w, i) => {
            const h = w.count === 0 ? 2 : Math.max(4, (w.count / most) * (BAR_H - 2));
            return (
              <rect
                key={w.start.toISOString()}
                x={i * slot + (slot - barWidth) / 2}
                y={BAR_H - h}
                width={barWidth}
                height={h}
                rx="2"
                className={w.count === 0 ? "fill-line" : "fill-primary"}
              />
            );
          })}
        </svg>
        <figcaption className="flex justify-between text-[12px] text-muted">
          <span>Games per week</span>
          <span>This week: {weeks[weeks.length - 1]?.count ?? 0}</span>
        </figcaption>
      </figure>
      <dl className="grid grid-cols-2 gap-2">
        <div className="flex flex-col gap-0.5 rounded-xl bg-bg px-3 py-2">
          <dt className="text-[13px] font-bold text-muted">Doubles · singles</dt>
          <dd className="text-[24px] leading-none font-extrabold tabular-nums [font-stretch:75%]">
            {doubles} · {singles}
          </dd>
        </div>
        <div className="flex flex-col gap-0.5 rounded-xl bg-bg px-3 py-2">
          <dt className="text-[13px] font-bold text-muted">Busiest day</dt>
          <dd className="text-[20px] leading-tight font-extrabold">{day ?? "–"}</dd>
        </div>
      </dl>
    </div>
  );
}
