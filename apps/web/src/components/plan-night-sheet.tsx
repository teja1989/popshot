"use client";

import { useRef, useState, type ReactNode, type SubmitEvent } from "react";

import { apiPatch, apiPost, ApiError } from "@/lib/api-client";
import { initialWhere, inOrder, wherePayload, type Where } from "@/lib/courts";
import type { GroupDetail } from "@/lib/groups";
import { toLocalInput } from "@/lib/games";
import { defaultStart, MAX_WEEKS, NOTE_MAX, VENUE_MAX, type Night } from "@/lib/nights";

import { useSignedIn } from "./auth";
import { buttonClass } from "./ui/button";
import { Sheet } from "./ui/sheet";
import { useApiGet } from "./use-api";

const field = "min-h-12 rounded-xl border border-line bg-bg px-4 text-field text-ink placeholder:text-muted";
const chip =
  "flex min-h-11 cursor-pointer items-center justify-center rounded-full border border-line px-4 text-body font-bold text-muted " +
  "has-[:checked]:border-primary has-[:checked]:bg-primary has-[:checked]:text-on-primary " +
  "has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-primary";

/** Plan a meetup (optionally weekly), or change one. */
export function PlanNightSheet({
  groupId,
  trigger,
  editing,
  lastVenue,
  onSaved,
}: {
  groupId: string;
  trigger: ReactNode;
  // The night being changed; planning a new one when left out.
  editing?: Night;
  // Pre-filled for a new night: where the crew played last.
  lastVenue?: string;
  onSaved: (night: Night) => void;
}) {
  const { user } = useSignedIn();
  const [open, setOpen] = useState(false);
  const venueRef = useRef<HTMLInputElement>(null);
  const [when, setWhen] = useState("");
  // The crew's saved courts, default first (already loaded on the crew's pages).
  const crew = useApiGet<GroupDetail>(`/v1/groups/${groupId}`).result;
  const courts = crew.kind === "ready" ? inOrder(crew.data.courts ?? []) : [];
  const [where, setWhere] = useState<Where>({ kind: "elsewhere", venue: "" });
  const [spots, setSpots] = useState("");
  const [weekly, setWeekly] = useState(false);
  const [weeks, setWeeks] = useState(4);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  function reset() {
    setWhen(toLocalInput(editing ? new Date(editing.starts_at) : defaultStart()));
    setWhere(initialWhere(courts, editing, lastVenue));
    setSpots(editing?.spots ? String(editing.spots) : "");
    setWeekly(false);
    setWeeks(4);
    setNote(editing?.note ?? "");
    setProblem(null);
  }

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const place = wherePayload(where);
    if (!place.venue) {
      setProblem("Say where you're playing.");
      venueRef.current?.focus();
      return;
    }
    const startsAt = new Date(when);
    if (Number.isNaN(startsAt.getTime())) {
      setProblem("Pick a day and time.");
      return;
    }
    const limit = spots.trim() ? Number(spots) : null;
    if (limit !== null && (!Number.isInteger(limit) || limit < 2 || limit > 64)) {
      setProblem("Spots can be from 2 to 64, or leave it empty for no limit.");
      return;
    }
    setSaving(true);
    setProblem(null);
    const body = { starts_at: startsAt.toISOString(), ...place, note: note.trim() || null, spots: limit };
    try {
      const saved = editing
        ? await apiPatch<Night>(user, `/v1/groups/${groupId}/nights/${editing.id}`, body)
        : (await apiPost<Night[]>(user, `/v1/groups/${groupId}/nights`, { ...body, weeks: weekly ? weeks : 1 }))[0];
      setOpen(false);
      if (saved) {
        onSaved(saved);
      }
    } catch (error) {
      setProblem(
        error instanceof ApiError && error.detail
          ? error.detail
          : error instanceof ApiError && error.status === 422
            ? "Something there won't work. Check the time and the venue."
            : "We couldn't save that just now. Try again in a moment.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet
      trigger={trigger}
      open={open}
      onOpenChange={(next) => {
        if (next) {
          reset();
        }
        setOpen(next);
      }}
      title={editing ? "Change this meetup" : "Plan a meetup"}
      description={
        editing ? "Everyone's answers stay as they are." : "Your crew gets a notification to say if they're in."
      }
      fullOnPhone
    >
      <form className="flex flex-col gap-5" onSubmit={(event) => void submit(event)} noValidate>
        <label className="flex flex-col gap-2">
          <span className="text-body font-bold">When</span>
          <input
            type="datetime-local"
            value={when}
            onChange={(event) => {
              setWhen(event.target.value);
            }}
            className={field}
          />
        </label>
        {courts.length > 0 ? (
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-body font-bold">Where</legend>
            <div className="flex flex-wrap gap-2">
              {courts.map((court) => (
                <label key={court.id} className={chip}>
                  <input
                    type="radio"
                    name="where"
                    className="sr-only"
                    checked={where.kind === "court" && where.court.id === court.id}
                    onChange={() => {
                      setWhere({ kind: "court", court });
                    }}
                  />
                  {court.label}
                </label>
              ))}
              <label className={chip}>
                <input
                  type="radio"
                  name="where"
                  className="sr-only"
                  checked={where.kind === "elsewhere"}
                  onChange={() => {
                    setWhere({ kind: "elsewhere", venue: "" });
                    window.setTimeout(() => venueRef.current?.focus(), 0);
                  }}
                />
                Somewhere else
              </label>
            </div>
            {where.kind === "elsewhere" && (
              <input
                ref={venueRef}
                aria-label="Other venue"
                value={where.venue}
                onChange={(event) => {
                  setWhere({ kind: "elsewhere", venue: event.target.value });
                }}
                maxLength={VENUE_MAX}
                autoComplete="off"
                placeholder="Riverside Park courts"
                className={field}
              />
            )}
          </fieldset>
        ) : (
          <label className="flex flex-col gap-2">
            <span className="text-body font-bold">Where</span>
            <input
              ref={venueRef}
              value={where.kind === "elsewhere" ? where.venue : ""}
              onChange={(event) => {
                setWhere({ kind: "elsewhere", venue: event.target.value });
              }}
              maxLength={VENUE_MAX}
              autoComplete="off"
              placeholder="Riverside Park courts"
              className={field}
            />
          </label>
        )}
        <label className="flex flex-col gap-2">
          <span className="text-body font-bold">Spots</span>
          <input
            type="number"
            inputMode="numeric"
            min={2}
            max={64}
            value={spots}
            onChange={(event) => {
              setSpots(event.target.value);
            }}
            placeholder="No limit"
            className={`${field} w-40`}
          />
          <span className="text-small text-muted">
            When it&apos;s full, others join a waitlist and move up if someone drops out.
          </span>
        </label>
        {!editing && (
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex min-h-11 cursor-pointer items-center gap-3 text-body font-bold">
              <input
                type="checkbox"
                role="switch"
                checked={weekly}
                onChange={(event) => {
                  setWeekly(event.target.checked);
                }}
                className="relative h-[26px] w-11 cursor-pointer appearance-none rounded-full bg-line transition-colors duration-200 before:absolute before:top-[3px] before:left-[3px] before:size-5 before:rounded-full before:bg-surface before:shadow-sm before:transition-transform before:duration-200 before:ease-court checked:bg-primary checked:before:translate-x-[18px]"
              />
              Repeat weekly
            </label>
            {weekly && (
              <label className="flex items-center gap-2 text-body">
                for
                <select
                  value={weeks}
                  onChange={(event) => {
                    setWeeks(Number(event.target.value));
                  }}
                  className="min-h-11 rounded-xl border border-line bg-bg px-3 text-field font-bold text-ink"
                >
                  {Array.from({ length: MAX_WEEKS - 1 }, (_, i) => i + 2).map((n) => (
                    <option key={n} value={n}>
                      {n} weeks
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
        )}
        <label className="flex flex-col gap-2">
          <span className="text-body font-bold">Note (optional)</span>
          <input
            value={note}
            onChange={(event) => {
              setNote(event.target.value);
            }}
            maxLength={NOTE_MAX}
            autoComplete="off"
            placeholder="Bring balls · drinks after"
            className={field}
          />
        </label>
        <p role="alert" className="min-h-6 text-body text-warn">
          {problem}
        </p>
        <button type="submit" className={buttonClass("primary", "h-14 w-full")} disabled={saving}>
          {saving ? "Saving…" : editing ? "Save changes" : "Plan it"}
        </button>
      </form>
    </Sheet>
  );
}
