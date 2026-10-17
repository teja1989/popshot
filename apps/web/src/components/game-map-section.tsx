"use client";

import Link from "next/link";
import { useId, useState } from "react";

import { apiPut, ApiError } from "@/lib/api-client";
import {
  BOX_CORNERS,
  BOXES,
  describePoint,
  formPosition,
  GOAL_MAX,
  GOAL_MIN,
  MAP_FEATURE,
  mapSummary,
  plotted,
  rhythmPosition,
  weekLabel,
  type Box,
  type GameMap,
  type MapPoint,
} from "@/lib/game-map";

import { useSignedIn } from "./auth";
import { useYouFeature } from "./features";
import { buttonClass } from "./ui/button";
import { Sheet } from "./ui/sheet";
import { useApiGet } from "./use-api";

// The chart's own square, in SVG units; the plot sits inside the padding.
const SIZE = 320;
const PAD = 28;
const PLOT = SIZE - 2 * PAD;

const toX = (position: number) => PAD + position * PLOT;
const toY = (position: number) => PAD + (1 - position) * PLOT;

/** Your game map: where your game is, for you alone (docs/game-map.md). */
export function GameMapSection() {
  const on = useYouFeature(MAP_FEATURE);
  if (!on) {
    return null;
  }
  return <GameMapCard />;
}

function GameMapCard() {
  const { result, reload } = useApiGet<GameMap>("/v1/me/map");
  const [asTable, setAsTable] = useState(false);

  return (
    <section aria-labelledby="map-heading" className="flex animate-rise flex-col gap-3 [animation-delay:15ms]">
      <div className="flex flex-col gap-1">
        <h2 id="map-heading" className="text-title-sm font-bold text-ink">
          Your game map
        </h2>
        <p className="text-small text-muted">
          How often you play, and how your results compare with what your crew points expected. Only you see it.
        </p>
      </div>
      <div className="flex flex-col gap-4 rounded-3xl border border-transparent bg-surface shadow-card p-5">
        {result.kind === "loading" && <p className="text-muted">Loading your map…</p>}
        {result.kind === "error" && (
          <p role="alert" className="text-warn">
            We couldn&apos;t load your map just now.
          </p>
        )}
        {result.kind === "ready" && (
          <>
            {asTable ? <MapTable map={result.data} /> : <MapChart map={result.data} />}
            <NowBox map={result.data} />
            <div className="flex flex-wrap items-center justify-between gap-3">
              <GoalSheet map={result.data} onSaved={reload} />
              <button
                type="button"
                className={buttonClass("quiet", "min-h-11 px-4 text-body")}
                aria-pressed={asTable}
                onClick={() => {
                  setAsTable(!asTable);
                }}
              >
                {asTable ? "Show the map" : "Show as a table"}
              </button>
            </div>
          </>
        )}
      </div>
    </section>
  );
}

function MapChart({ map }: { map: GameMap }) {
  const titleId = useId();
  const points = plotted(map);
  const [active, setActive] = useState<number | null>(null);
  const coords = points.map((p) => ({ x: toX(rhythmPosition(p.per_week, map.goal)), y: toY(formPosition(p.form)) }));
  const shown = active === null ? null : points[active];
  const at = active === null ? null : coords[active];

  return (
    <figure className="relative m-0">
      <svg
        viewBox={`0 0 ${String(SIZE)} ${String(SIZE)}`}
        className="block aspect-square w-full"
        role="group"
        aria-labelledby={titleId}
      >
        <title id={titleId}>{mapSummary(map)}</title>
        {/* The plot area, and the two middle lines: your goal, and as expected. */}
        <rect x={PAD} y={PAD} width={PLOT} height={PLOT} fill="none" stroke="var(--color-line)" strokeWidth={1} />
        <line x1={SIZE / 2} y1={PAD} x2={SIZE / 2} y2={SIZE - PAD} stroke="var(--color-line)" strokeWidth={1} />
        <line x1={PAD} y1={SIZE / 2} x2={SIZE - PAD} y2={SIZE / 2} stroke="var(--color-line)" strokeWidth={1} />
        {(Object.keys(BOX_CORNERS) as Box[]).map((box) => {
          const { right, top } = BOX_CORNERS[box];
          return (
            <text
              key={box}
              x={right ? SIZE - PAD - 8 : PAD + 8}
              y={top ? PAD + 18 : SIZE - PAD - 10}
              textAnchor={right ? "end" : "start"}
              className="fill-muted text-[11px] font-bold"
            >
              {BOXES[box].title}
            </text>
          );
        })}
        <text x={SIZE / 2} y={SIZE - 8} textAnchor="middle" className="fill-muted text-[11px]">
          {`Games a week · your goal ${String(map.goal)} in the middle`}
        </text>
        <text
          x={10}
          y={SIZE / 2}
          textAnchor="middle"
          transform={`rotate(-90 10 ${String(SIZE / 2)})`}
          className="fill-muted text-[11px]"
        >
          Results vs expected
        </text>
        {coords.length > 1 && (
          <polyline
            points={coords.map((c) => `${String(c.x)},${String(c.y)}`).join(" ")}
            fill="none"
            stroke="var(--color-trail)"
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        )}
        {coords.map((c, i) => {
          const isNow = i === coords.length - 1 && points[i] === map.points.at(-1);
          return (
            <circle
              key={points[i]?.ending}
              cx={c.x}
              cy={c.y}
              r={isNow ? 7 : 5}
              fill={isNow ? "var(--color-primary)" : "var(--color-trail)"}
              stroke="var(--color-surface)"
              strokeWidth={2}
            />
          );
        })}
        {coords.length > 0 && points.at(-1) === map.points.at(-1) && (
          <text
            // Beside the dot, on whichever side has room.
            x={(coords.at(-1)?.x ?? 0) + ((coords.at(-1)?.x ?? 0) > SIZE * 0.7 ? -12 : 12)}
            y={(coords.at(-1)?.y ?? 0) + 4}
            textAnchor={(coords.at(-1)?.x ?? 0) > SIZE * 0.7 ? "end" : "start"}
            className="fill-ink text-[12px] font-bold"
          >
            Now
          </text>
        )}
        {/* Hover and keyboard targets, bigger than the dots (24px or more). */}
        {coords.map((c, i) => {
          const p = points[i];
          if (!p) {
            return null;
          }
          return (
            <circle
              key={`hit-${p.ending}`}
              cx={c.x}
              cy={c.y}
              r={14}
              fill="transparent"
              tabIndex={0}
              role="img"
              aria-label={`${weekLabel(p.ending)}: ${describePoint(p)}`}
              className="cursor-default outline-none focus-visible:stroke-primary focus-visible:stroke-2"
              onPointerEnter={() => {
                setActive(i);
              }}
              onPointerLeave={() => {
                setActive(null);
              }}
              onFocus={() => {
                setActive(i);
              }}
              onBlur={() => {
                setActive(null);
              }}
            />
          );
        })}
      </svg>
      {shown && at && (
        <div
          role="tooltip"
          className="pointer-events-none absolute z-10 w-max max-w-[14rem] -translate-x-1/2 rounded-xl bg-ink px-3 py-2 text-small text-bg shadow-card"
          style={{
            left: `${String((at.x / SIZE) * 100)}%`,
            top: `${String((at.y / SIZE) * 100)}%`,
            transform: `translate(-50%, ${at.y < SIZE / 2 ? "16px" : "calc(-100% - 16px)"})`,
          }}
        >
          <span className="block font-bold">{weekLabel(shown.ending)}</span>
          {describePoint(shown)}
        </div>
      )}
    </figure>
  );
}

function MapTable({ map }: { map: GameMap }) {
  return (
    <table className="w-full text-left text-body">
      <caption className="sr-only">Your game map, week by week</caption>
      <thead>
        <tr className="text-small text-muted">
          <th scope="col" className="py-2 font-bold">
            Week
          </th>
          <th scope="col" className="py-2 font-bold">
            Games a week
          </th>
          <th scope="col" className="py-2 font-bold">
            Results
          </th>
        </tr>
      </thead>
      <tbody>
        {[...map.points].reverse().map((p: MapPoint) => (
          <tr key={p.ending} className="border-t border-line">
            <th scope="row" className="py-2 font-normal">
              {weekLabel(p.ending)}
            </th>
            <td className="py-2 tabular-nums">{String(Math.round(p.per_week * 10) / 10)}</td>
            <td className="py-2">{p.box ? BOXES[p.box].title : "Not enough games yet"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function NowBox({ map }: { map: GameMap }) {
  const now = map.points.at(-1);
  if (!now?.box) {
    return <p className="text-body text-muted">{mapSummary(map)}</p>;
  }
  const box = BOXES[now.box];
  return (
    <div className="flex flex-col gap-2">
      <p className="text-lead font-bold text-ink">{box.title}</p>
      <p className="text-body text-muted">
        {box.means} {`Now: ${describePoint(now)}.`}
      </p>
      <Link href={box.next.href} className={buttonClass("primary", "self-start")}>
        {box.next.label}
      </Link>
    </div>
  );
}

function GoalSheet({ map, onSaved }: { map: GameMap; onSaved: () => void }) {
  const { user } = useSignedIn();
  const [open, setOpen] = useState(false);
  const [goal, setGoal] = useState(map.goal);
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const choices = Array.from({ length: GOAL_MAX - GOAL_MIN + 1 }, (_, i) => GOAL_MIN + i);

  async function save() {
    setSaving(true);
    setProblem(null);
    try {
      await apiPut(user, "/v1/me/map/goal", { weekly_games: goal });
      // The boxes depend on the goal: read the map again.
      onSaved();
      setOpen(false);
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "We couldn't save your goal just now.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet
      trigger={
        <button type="button" className={buttonClass("quiet", "min-h-11 px-4 text-body")}>
          {`Goal: ${String(map.goal)} game${map.goal === 1 ? "" : "s"} a week`}
        </button>
      }
      open={open}
      onOpenChange={(next) => {
        if (next) {
          setGoal(map.goal);
          setProblem(null);
        }
        setOpen(next);
      }}
      title="Your weekly goal"
      description="How many games a week you'd like to play. It's the middle line of your map, and only you see it."
    >
      <form
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          event.stopPropagation();
          void save();
        }}
      >
        <label className="flex flex-col gap-2">
          <span className="text-body font-bold">Games a week</span>
          <select
            value={goal}
            onChange={(event) => {
              setGoal(Number(event.target.value));
            }}
            className="min-h-12 rounded-xl border border-line bg-bg px-4 text-field text-ink"
          >
            {choices.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        {problem && (
          <p role="alert" className="text-body text-warn">
            {problem}
          </p>
        )}
        <button type="submit" className={buttonClass("primary")} disabled={saving}>
          {saving ? "Saving…" : "Save goal"}
        </button>
      </form>
    </Sheet>
  );
}
