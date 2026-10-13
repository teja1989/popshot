"use client";

import { useState, type ReactNode } from "react";

import { byDay, dayKey, daysShown, rangeOf, step, titleOf, type Span } from "@/lib/calendar";
import type { Match } from "@/lib/games";
import type { GroupSummary } from "@/lib/groups";
import type { Night } from "@/lib/nights";
import { recall, remember } from "@/lib/remember";

import { NightCard } from "./night-card";
import { buttonClass } from "./ui/button";
import { segmentOption, segmentTrack } from "./ui/segmented";
import { useApiGet } from "./use-api";

interface Calendar {
  games: Match[];
  nights: Night[];
}

const SPANS: readonly Span[] = ["week", "month"];
const SPAN_KEY = "popshot.calendar.span";
const WEEKDAYS = ["S", "M", "T", "W", "T", "F", "S"];

/**
 * The group's games and play nights by day: a week (the default) or a month, remembered on
 * this device. Tap a day to see its nights and games, as the same cards as the list.
 */
export function GamesCalendar({
  group,
  renderGame,
}: {
  group: GroupSummary;
  renderGame: (match: Match, reload: () => void) => ReactNode;
}) {
  const [span, setSpan] = useState<Span>(() => recall(SPAN_KEY, SPANS, "week"));
  const [anchor, setAnchor] = useState(() => new Date());
  const [selected, setSelected] = useState(() => dayKey(new Date()));
  const days = daysShown(span, anchor);
  const { start, end } = rangeOf(days);
  const path =
    `/v1/groups/${group.id}/calendar?start=${encodeURIComponent(start.toISOString())}&end=${encodeURIComponent(end.toISOString())}` as const;
  const { result, reload, replace } = useApiGet<Calendar>(path);
  const data = result.kind === "ready" ? result.data : null;
  const gamesByDay = byDay(data?.games ?? [], (g) => g.played_at);
  const nightsByDay = byDay(data?.nights ?? [], (n) => n.starts_at);
  const today = dayKey(new Date());

  function moveTo(nextSpan: Span, nextAnchor: Date) {
    setSpan(nextSpan);
    setAnchor(nextAnchor);
    const shown = daysShown(nextSpan, nextAnchor).map(dayKey);
    // Keep the chosen day if it's still shown; otherwise today, or the first day shown.
    setSelected((current) => (shown.includes(current) ? current : shown.includes(today) ? today : (shown[0] ?? today)));
  }

  const selectedDate = days.find((d) => dayKey(d) === selected) ?? new Date();
  const dayNights = nightsByDay.get(selected) ?? [];
  const dayGames = gamesByDay.get(selected) ?? [];

  return (
    <section aria-label="Calendar" className="flex animate-rise flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label={`Previous ${span}`}
            className={buttonClass("quiet", "min-h-11 w-11 px-0")}
            onClick={() => {
              moveTo(span, step(span, anchor, -1));
            }}
          >
            ‹
          </button>
          <h2 aria-live="polite" className="min-w-36 text-center text-lead font-extrabold">
            {titleOf(span, anchor)}
          </h2>
          <button
            type="button"
            aria-label={`Next ${span}`}
            className={buttonClass("quiet", "min-h-11 w-11 px-0")}
            onClick={() => {
              moveTo(span, step(span, anchor, 1));
            }}
          >
            ›
          </button>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="min-h-11 cursor-pointer rounded-xl px-3 text-body font-bold text-primary"
            onClick={() => {
              setSelected(today);
              moveTo(span, new Date());
            }}
          >
            Today
          </button>
          <fieldset className={`${segmentTrack} grid-cols-2`}>
            <legend className="sr-only">Show</legend>
            {SPANS.map((value) => (
              <label key={value} className={`${segmentOption} px-3`}>
                <input
                  type="radio"
                  name="calendar-span"
                  checked={span === value}
                  onChange={() => {
                    remember(SPAN_KEY, value);
                    moveTo(value, anchor);
                  }}
                  className="sr-only"
                />
                {value === "week" ? "Week" : "Month"}
              </label>
            ))}
          </fieldset>
        </div>
      </div>

      <div className="rounded-2xl border border-line bg-surface p-2">
        <div aria-hidden="true" className="grid grid-cols-7 pb-1 text-center text-meta font-bold text-muted">
          {WEEKDAYS.map((d, i) => (
            <span key={i}>{d}</span>
          ))}
        </div>
        <div className="grid grid-cols-7 gap-1">
          {days.map((day) => {
            const key = dayKey(day);
            const games = gamesByDay.get(key)?.length ?? 0;
            const nights = nightsByDay.get(key) ?? [];
            const live = nights.filter((n) => !n.cancelled).length;
            const outside = span === "month" && day.getMonth() !== anchor.getMonth();
            const label = [
              day.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" }),
              games ? `${String(games)} game${games === 1 ? "" : "s"}` : "",
              live ? `${String(live)} meetup${live === 1 ? "" : "s"}` : "",
            ]
              .filter(Boolean)
              .join(", ");
            return (
              <button
                key={key}
                type="button"
                aria-label={label}
                aria-pressed={key === selected}
                onClick={() => {
                  setSelected(key);
                }}
                className={`flex cursor-pointer flex-col items-center gap-1 rounded-xl py-2 ${
                  key === selected ? "bg-primary text-on-primary" : outside ? "text-muted" : "text-ink"
                } ${span === "week" ? "min-h-16" : "min-h-12"}`}
              >
                <span
                  className={`text-body tabular-nums ${key === today ? "font-extrabold underline" : "font-bold"}`}
                >
                  {day.getDate()}
                </span>
                <span aria-hidden="true" className="flex h-2 items-center gap-1">
                  {games > 0 && <span className="size-2 rounded-full bg-ball" />}
                  {live > 0 && <span className="size-2 rounded-full border-2 border-current" />}
                </span>
              </button>
            );
          })}
        </div>
      </div>
      <p className="-mt-2 flex gap-4 text-meta text-muted">
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="size-2 rounded-full bg-ball" /> Games
        </span>
        <span className="flex items-center gap-1.5">
          <span aria-hidden="true" className="size-2 rounded-full border-2 border-muted" /> Meetups
        </span>
      </p>

      <section aria-label="Selected day" className="flex flex-col gap-3">
        <h3 className="text-label font-bold tracking-[0.1em] text-muted uppercase">
          {selectedDate.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
        </h3>
        {result.kind === "loading" && <p className="text-muted">Loading…</p>}
        {result.kind === "error" && (
          <div role="alert" className="flex items-center gap-3">
            <p>We couldn&apos;t load the calendar just now.</p>
            <button type="button" className={buttonClass("quiet", "min-h-10 px-3 text-body")} onClick={reload}>
              Try again
            </button>
          </div>
        )}
        {data && dayNights.length === 0 && dayGames.length === 0 && <p className="text-muted">Nothing on this day.</p>}
        {dayNights.map((night) => (
          <NightCard
            key={night.id}
            night={night}
            onChange={(changed) => {
              if (data) {
                replace({ ...data, nights: data.nights.map((n) => (n.id === changed.id ? changed : n)) });
              }
            }}
          />
        ))}
        {dayGames.length > 0 && <ul className="flex flex-col gap-3">{dayGames.map((m) => renderGame(m, reload))}</ul>}
      </section>
    </section>
  );
}
