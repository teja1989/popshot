"use client";

import Link from "next/link";
import { useState } from "react";

import { share, shortDate } from "@/lib/admin";
import {
  crewSteps,
  peopleSteps,
  percent,
  PERIODS,
  SOURCE_LABEL,
  spreadPerActive,
  STAGE_LABEL,
  waitText,
  type CrewStage,
  type Funnel,
  type Loops,
  type Step,
} from "@/lib/admin-funnel";

import { AdminGate, AdminMain, Section, Stat, Table } from "./admin-ui";
import { segmentOption, segmentTrack } from "./ui/segmented";
import { useApiGet } from "./use-api";

/**
 * How new crews and people get going, where they came from, and how sharing spreads.
 * Admin only: the API answers 404 to anyone else, shown as "not found".
 */
export function AdminFunnelView() {
  const [weeks, setWeeks] = useState<number>(4);
  const funnel = useApiGet<Funnel>(`/v1/admin/funnel?weeks=${String(weeks)}`);
  const status = funnel.result.kind === "error" ? funnel.result.status : null;

  return (
    <AdminGate status={status} onSignedIn={funnel.reload}>
      <AdminMain>
        <header className="flex animate-rise flex-col gap-1">
          <Link href="/admin" className="self-start text-small font-bold text-primary">
            ← Admin
          </Link>
          <h1 className="text-title-lg leading-tight font-extrabold">Funnel</h1>
          <p className="text-body text-muted">
            How new crews and people get going, and where they come from. Visit counts are approximate.
          </p>
        </header>
        <fieldset className={`${segmentTrack} grid-cols-3 self-start`}>
          <legend className="sr-only">Period</legend>
          {PERIODS.map((n) => (
            <label key={n} className={segmentOption}>
              <input
                type="radio"
                name="weeks"
                className="sr-only"
                checked={weeks === n}
                onChange={() => {
                  setWeeks(n);
                }}
              />
              {n} weeks
            </label>
          ))}
        </fieldset>
        {funnel.result.kind === "loading" && <p className="text-muted">Loading the funnel…</p>}
        {funnel.result.kind === "error" && status !== 404 && status !== 403 && (
          <p role="alert" className="text-warn">
            We couldn&apos;t load the funnel just now.
          </p>
        )}
        {funnel.result.kind === "ready" && <FunnelSections funnel={funnel.result.data} />}
      </AdminMain>
    </AdminGate>
  );
}

function FunnelSections({ funnel }: { funnel: Funnel }) {
  return (
    <>
      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="New crews">
          <Steps label="New crews, step by step" steps={crewSteps(funnel.crews)} />
          <p className="text-small text-muted">
            First game after starting: {waitText(funnel.crews.median_hours_to_first_game)} (median).
          </p>
        </Section>
        <Section title="New people">
          <Steps label="New people, step by step" steps={peopleSteps(funnel.people)} />
        </Section>
      </div>
      <Section title="Where people came from">
        <Table
          label="New people by where they came from"
          head={["From", "Visits", "Signed up", "In a crew", "Played", "Visit → sign-up"]}
          rows={funnel.sources.map((s) => [
            SOURCE_LABEL[s.source],
            s.visits,
            s.signed_up,
            s.in_crew,
            s.played,
            share(s.signed_up, s.visits),
          ])}
        />
      </Section>
      <LoopsSection loops={funnel.loops} />
      <Section title="Active crews each week">
        <WeeklyCrews weeks={funnel.active_crews} />
      </Section>
      <StagesSection stages={funnel.stages} />
    </>
  );
}

function Steps({ label, steps }: { label: string; steps: Step[] }) {
  return (
    <ol aria-label={label} className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4">
      {steps.map((s) => (
        <li key={s.label} className="flex flex-col gap-1">
          <span className="flex items-baseline justify-between gap-3 text-small">
            <span className="font-bold">{s.label}</span>
            <span className="tabular-nums">
              <strong>{s.count}</strong> <span className="text-muted">· {share(s.count, s.of)}</span>
            </span>
          </span>
          {/* An SVG width, not a style: no inline styles under the CSP. */}
          <svg viewBox="0 0 100 6" preserveAspectRatio="none" aria-hidden="true" className="h-2 w-full">
            <rect width="100" height="6" rx="3" className="fill-chip" />
            <rect width={percent(s.count, s.of)} height="6" rx="3" className="fill-primary" />
          </svg>
          {s.note && <span className="text-meta text-muted">{s.note}</span>}
        </li>
      ))}
    </ol>
  );
}

function LoopsSection({ loops }: { loops: Loops }) {
  return (
    <Section title="Sharing">
      <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Recaps shared" value={loops.recaps_shared} />
        <Stat label="Shared recaps opened" value={loops.share_views} note="approximate" />
        <Stat label="“Try Popshot” taps" value={loops.try_taps} note={share(loops.try_taps, loops.share_views)} />
        <Stat label="Sign-ups from a recap" value={loops.recap_signups} />
        <Stat label="Invite links made" value={loops.invite_links} note={`${String(loops.link_joins)} joins`} />
        <Stat label="Direct invites" value={loops.direct_invites} note={`${String(loops.direct_accepted)} accepted`} />
        <Stat
          label="Sign-ups from invites"
          value={loops.invite_signups}
          note={`${String(loops.code_signups)} by code`}
        />
        <div className="flex flex-col gap-1 rounded-2xl border border-line bg-surface p-4">
          <dt className="text-small text-muted">New players per active player</dt>
          <dd className="text-title-lg leading-none font-extrabold font-numeral">{spreadPerActive(loops)}</dd>
          <dd className="text-meta text-muted">{loops.active_users} active in the period</dd>
        </div>
      </dl>
    </Section>
  );
}

function WeeklyCrews({ weeks }: { weeks: Funnel["active_crews"] }) {
  const most = Math.max(1, ...weeks.map((w) => w.active_crews));
  return (
    <figure className="flex flex-col gap-2 rounded-2xl border border-line bg-surface p-4">
      <svg
        viewBox={`0 0 ${String(weeks.length * 10)} 40`}
        preserveAspectRatio="none"
        aria-hidden="true"
        className="h-28 w-full"
      >
        {weeks.map((w, i) => {
          const h = Math.max(1, Math.round((38 * w.active_crews) / most));
          return (
            <rect key={w.week_start} x={i * 10 + 2} y={40 - h} width="6" height={h} className="fill-primary" />
          );
        })}
      </svg>
      <Table
        label="Active crews each week, newest first"
        head={["Week of", "Active crews"]}
        rows={[...weeks].reverse().map((w) => [shortDate(w.week_start), w.active_crews])}
      />
    </figure>
  );
}

function StagesSection({ stages }: { stages: CrewStage[] }) {
  return (
    <Section title={`Newer crews (${String(stages.length)})`}>
      {stages.length === 0 ? (
        <p className="text-muted">No crews started in the last 90 days.</p>
      ) : (
        <ul aria-label="Newer crews, newest first" className="flex flex-col rounded-2xl border border-line bg-surface">
          {stages.map((c) => (
            <li key={c.id} className="flex flex-col gap-1 border-b border-line px-4 py-3 last:border-b-0">
              <span className="flex flex-wrap items-center justify-between gap-2">
                <Link href={`/admin/crews/${c.id}`} className="truncate font-bold text-ink">
                  {c.name}
                </Link>
                <span className="rounded-full bg-chip px-2.5 py-0.5 text-meta font-bold">{STAGE_LABEL[c.stage]}</span>
              </span>
              <span className="text-small text-muted tabular-nums">
                Started {shortDate(c.created_at)} · {c.members} member{c.members === 1 ? "" : "s"} · {c.games} game
                {c.games === 1 ? "" : "s"}
                {c.last_game_at ? ` · last ${shortDate(c.last_game_at)}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}
