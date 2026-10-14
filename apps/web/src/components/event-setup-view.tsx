"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { apiPost, ApiError } from "@/lib/api-client";
import {
  FORMATS,
  formatInfo,
  MAX_COURTS,
  MAX_PLAYERS,
  MIN_PLAYERS,
  NAME_MAX,
  roundShape,
  SEEDING_LABEL,
  shapeLine,
  suggestFormat,
  type CrewEvent,
  type EventKind,
  type NewEventBody,
  type Seeding,
  type Vibe,
} from "@/lib/events";
import type { Player } from "@/lib/games";
import type { GroupDetail } from "@/lib/groups";
import { nightWhen, type Night } from "@/lib/nights";
import type { BestOf, PointsTo } from "@/lib/scoring";

import { AddGuestInline } from "./add-guest-inline";
import { useSignedIn } from "./auth";
import { useFeature, useFeaturesLoaded } from "./features";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";
import { segmentOption, segmentTrack } from "./ui/segmented";

const SECTION = "flex flex-col gap-3";
const HEADING = "text-title-sm font-bold text-ink";

/** Start an event: format, who's playing, courts, details and rules, then start. */
export function EventSetupView({ groupId }: { groupId: string }) {
  const group = useApiGet<GroupDetail>(`/v1/groups/${groupId}`);
  const players = useApiGet<Player[]>(`/v1/groups/${groupId}/players`);
  const nights = useApiGet<Night[]>(`/v1/groups/${groupId}/nights`);
  const loaded = useFeaturesLoaded();
  const shuffleOn = useFeature("events.shuffle", groupId);
  const riverOn = useFeature("events.river", groupId);
  const available = FORMATS.filter((f) => (f.kind === "shuffle" ? shuffleOn : riverOn)).map((f) => f.kind);

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <header className="flex flex-col gap-1">
        <Link href="/play" className="self-start text-small font-bold text-primary">
          ← Play
        </Link>
        <h1 className="text-display-sm leading-tight font-extrabold tracking-[-0.02em] font-display">Start an event</h1>
      </header>
      {(group.result.kind === "loading" || players.result.kind === "loading" || !loaded) && (
        <p className="text-muted">Loading…</p>
      )}
      {(group.result.kind === "error" || players.result.kind === "error") && (
        <p role="alert" className="text-warn">
          We couldn&apos;t load your crew just now.
        </p>
      )}
      {loaded && group.result.kind === "ready" && players.result.kind === "ready" && (
        <Setup
          group={group.result.data}
          players={players.result.data}
          onGuestAdded={players.reload}
          nights={nights.result.kind === "ready" ? nights.result.data : []}
          available={available}
        />
      )}
    </main>
  );
}

function Setup({
  group,
  players,
  onGuestAdded,
  nights,
  available,
}: {
  group: GroupDetail;
  players: Player[];
  onGuestAdded: () => void;
  nights: Night[];
  available: EventKind[];
}) {
  const { user } = useSignedIn();
  const router = useRouter();
  const isAdmin = group.my_role === "lead" || group.my_role === "co_lead";
  // What was picked; with only one format switched on, that one.
  const [choice, setKind] = useState<EventKind | null>(null);
  const kind = choice ?? (available.length === 1 ? (available[0] ?? null) : null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [nightId, setNightId] = useState<string | null>(null);
  const [courts, setCourts] = useState(2);
  const [name, setName] = useState("");
  const [vibe, setVibe] = useState<Vibe>("social");
  const [seeding, setSeeding] = useState<Seeding>("random");
  const [pointsTo, setPointsTo] = useState<PointsTo>(group.default_points_to);
  const [winByTwo, setWinByTwo] = useState(group.default_win_by_two);
  const [bestOf, setBestOf] = useState<BestOf>(1);
  const [why, setWhy] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  const byUser = useMemo(
    () => new Map(players.flatMap((p) => (p.user_id ? [[p.user_id, p.id] as const] : []))),
    [players],
  );
  const count = picked.size;
  const shape = roundShape(count, courts);
  const placeholder = kind ? formatInfo(kind).name : "Event";
  const ready = kind !== null && count >= MIN_PLAYERS && count <= MAX_PLAYERS && shape.courts >= 1;

  if (!isAdmin) {
    return <p className="text-body">Only the crew&apos;s leads and co-leads can start an event.</p>;
  }
  if (available.length === 0) {
    return <p className="text-body">Events aren&apos;t switched on for {group.name} yet.</p>;
  }

  function toggle(id: string) {
    setPicked((now) => {
      const next = new Set(now);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function fromNight(id: string | null) {
    setNightId(id);
    const night = nights.find((n) => n.id === id);
    if (night) {
      setPicked(new Set(night.going.flatMap((g) => byUser.get(g.user_id) ?? [])));
    }
  }

  async function start() {
    if (!ready) {
      return;
    }
    setSaving(true);
    setProblem(null);
    const body: NewEventBody = {
      kind,
      name: name.trim() || placeholder,
      vibe,
      players: [...picked],
      courts,
      points_to: pointsTo,
      win_by_two: winByTwo,
      best_of: bestOf,
      night_id: nightId,
      seeding: kind === "river" ? seeding : null,
    };
    try {
      const made = await apiPost<CrewEvent>(user, `/v1/groups/${group.id}/events`, body);
      router.push(`/groups/${group.id}/events/${made.id}`);
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "That didn't start just now. Try again.");
      setSaving(false);
    }
  }

  return (
    <form
      className="flex flex-col gap-7"
      onSubmit={(event) => {
        event.preventDefault();
        void start();
      }}
    >
      <fieldset className={SECTION}>
        <legend className={`${HEADING} mb-3`}>1. Format</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {FORMATS.filter((f) => available.includes(f.kind)).map((f) => (
            <label
              key={f.kind}
              className="flex cursor-pointer flex-col gap-1 rounded-2xl border-2 border-line bg-surface p-4 has-[:checked]:border-primary has-[:focus-visible]:outline-3 has-[:focus-visible]:outline-primary"
            >
              <input
                type="radio"
                name="format"
                className="sr-only"
                checked={kind === f.kind}
                onChange={() => {
                  setKind(f.kind);
                  setWhy(null);
                }}
              />
              <span className="text-title-sm font-extrabold font-display">{f.name}</span>
              <span className="text-meta font-bold text-muted">{f.standard}</span>
              <span className="text-small">{f.blurb}</span>
            </label>
          ))}
        </div>
        {available.length > 1 && (
          <button
            type="button"
            className="self-start text-body font-bold text-primary disabled:text-muted"
            disabled={count < MIN_PLAYERS}
            onClick={() => {
              const pick = suggestFormat(count, courts, available);
              if (pick) {
                setKind(pick.kind);
                setWhy(`${formatInfo(pick.kind).name}: ${pick.why}`);
              }
            }}
          >
            Suggest for us
          </button>
        )}
        <p role="status" className="text-small text-muted empty:hidden">
          {why}
        </p>
      </fieldset>

      <fieldset className={SECTION}>
        <legend className={`${HEADING} mb-3`}>2. Who&apos;s playing</legend>
        {nights.length > 0 && (
          <label className="flex flex-col gap-1.5">
            <span className="text-small font-bold">From a meetup (optional)</span>
            <select
              value={nightId ?? ""}
              onChange={(event) => {
                fromNight(event.target.value || null);
              }}
              className="min-h-11 rounded-xl border border-line bg-surface px-3 text-field"
            >
              <option value="">No meetup</option>
              {nights.map((n) => (
                <option key={n.id} value={n.id}>
                  {nightWhen(n.starts_at)} · {n.venue} · {n.going.length} going
                </option>
              ))}
            </select>
          </label>
        )}
        <ul aria-label="Players" className="grid gap-1.5 sm:grid-cols-2">
          {players.map((p) => (
            <li key={p.id}>
              <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border border-line bg-surface px-3 has-[:checked]:border-primary">
                <input
                  type="checkbox"
                  checked={picked.has(p.id)}
                  onChange={() => {
                    toggle(p.id);
                  }}
                  className="size-5 accent-primary"
                />
                <span className="truncate font-bold">{p.display_name}</span>
                {p.is_guest && <span className="text-meta text-muted">guest</span>}
              </label>
            </li>
          ))}
        </ul>
        <p className="text-small text-muted">
          {count} picked
          {count > MAX_PLAYERS ? ` · up to ${String(MAX_PLAYERS)}` : ""}.
        </p>
        <AddGuestInline
          groupId={group.id}
          label="Someone not on Popshot? Add them as a guest"
          onAdded={(guest) => {
            setPicked((now) => new Set(now).add(guest.id));
            onGuestAdded();
          }}
        />
      </fieldset>

      <fieldset className={SECTION}>
        <legend className={`${HEADING} mb-3`}>3. Courts</legend>
        <div className={`${segmentTrack} grid-cols-6`}>
          {Array.from({ length: MAX_COURTS }, (_, i) => i + 1).map((n) => (
            <label key={n} className={segmentOption}>
              <input
                type="radio"
                name="courts"
                className="sr-only"
                checked={courts === n}
                onChange={() => {
                  setCourts(n);
                }}
              />
              {n}
            </label>
          ))}
        </div>
        <p className="text-small text-muted">{shapeLine(count, courts)}</p>
      </fieldset>

      <fieldset className={SECTION}>
        <legend className={`${HEADING} mb-3`}>4. Details</legend>
        <label className="flex flex-col gap-1.5">
          <span className="text-small font-bold">Name</span>
          <input
            value={name}
            maxLength={NAME_MAX}
            onChange={(event) => {
              setName(event.target.value);
            }}
            placeholder={placeholder}
            className="min-h-12 rounded-xl border border-line bg-surface px-4 text-field"
          />
        </label>
        <div className="flex flex-col gap-1.5">
          <span id="vibe-label" className="text-small font-bold">
            Results
          </span>
          <div role="radiogroup" aria-labelledby="vibe-label" className={`${segmentTrack} grid-cols-2`}>
            {(
              [
                ["social", "Social"],
                ["competitive", "Competitive"],
              ] as const
            ).map(([value, label]) => (
              <label key={value} className={segmentOption}>
                <input
                  type="radio"
                  name="vibe"
                  className="sr-only"
                  checked={vibe === value}
                  onChange={() => {
                    setVibe(value);
                  }}
                />
                {label}
              </label>
            ))}
          </div>
          <p className="text-meta text-muted">
            {vibe === "social"
              ? "No table: everyone sees their own results, then the recap."
              : "A table of wins inside this event only. It never goes on the crew page."}
          </p>
        </div>
        {kind === "river" && (
          <div className="flex flex-col gap-1.5">
            <span id="seeding-label" className="text-small font-bold">
              Starting courts
            </span>
            <div role="radiogroup" aria-labelledby="seeding-label" className={`${segmentTrack} grid-cols-3`}>
              {(Object.keys(SEEDING_LABEL) as Seeding[]).map((value) => (
                <label key={value} className={segmentOption}>
                  <input
                    type="radio"
                    name="seeding"
                    className="sr-only"
                    checked={seeding === value}
                    onChange={() => {
                      setSeeding(value);
                    }}
                  />
                  {SEEDING_LABEL[value]}
                </label>
              ))}
            </div>
            <p className="text-meta text-muted">Only used for the first round, and never shown to anyone.</p>
          </div>
        )}
      </fieldset>

      <fieldset className={SECTION}>
        <legend className={`${HEADING} mb-3`}>5. Rules</legend>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="flex flex-col gap-1.5">
            <span className="text-small font-bold">Games to</span>
            <select
              value={pointsTo}
              onChange={(event) => {
                setPointsTo(Number(event.target.value) as PointsTo);
              }}
              className="min-h-11 rounded-xl border border-line bg-surface px-3 text-field"
            >
              {[11, 15, 21].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="text-small font-bold">Best of</span>
            <select
              value={bestOf}
              onChange={(event) => {
                setBestOf(Number(event.target.value) as BestOf);
              }}
              className="min-h-11 rounded-xl border border-line bg-surface px-3 text-field"
            >
              {[1, 3, 5].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label className="flex min-h-11 cursor-pointer items-center gap-3 self-end">
            <input
              type="checkbox"
              checked={winByTwo}
              onChange={(event) => {
                setWinByTwo(event.target.checked);
              }}
              className="size-5 accent-primary"
            />
            <span className="font-bold">Win by 2</span>
          </label>
        </div>
      </fieldset>

      <div className="flex flex-col gap-3 rounded-2xl bg-chip p-4">
        <p className="text-body">
          {kind ? <strong>{formatInfo(kind).name}</strong> : "Pick a format"}
          {count >= MIN_PLAYERS ? ` · ${shapeLine(count, courts)}` : ` · pick at least ${String(MIN_PLAYERS)} players.`}
        </p>
        <button type="submit" disabled={!ready || saving} className={buttonClass("action", "h-14")}>
          {saving ? "Starting…" : "Start round 1"}
        </button>
        <p role="alert" className="text-body text-warn empty:hidden">
          {problem}
        </p>
      </div>
    </form>
  );
}
