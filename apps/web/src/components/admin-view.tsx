"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";

import { reachedWeeks, share, shortDate, type AdminGroup, type Overview } from "@/lib/admin";
import { reauthenticate } from "@/lib/firebase-client";

import { useSignedIn } from "./auth";
import { buttonClass } from "./ui/button";
import { useApiGet } from "./use-api";

/**
 * App-wide numbers for the owner. The API returns 404 to anyone who isn't an admin (shown
 * here as a plain "not found"), and 403 when the admin's sign-in is over 12 hours old.
 */
export function AdminView() {
  const overview = useApiGet<Overview>("/v1/admin/overview");
  const groups = useApiGet<AdminGroup[]>("/v1/admin/groups");
  const status = overview.result.kind === "error" ? overview.result.status : null;

  if (status === 404) {
    return <NotFound />;
  }
  if (status === 403) {
    return (
      <SignInAgain
        onDone={() => {
          overview.reload();
          groups.reload();
        }}
      />
    );
  }
  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 px-5 pt-6 pb-12 lg:max-w-4xl lg:px-8 lg:pt-10">
      <header className="flex animate-rise flex-col gap-1">
        <h1 className="text-[28px] leading-tight font-extrabold [font-stretch:110%]">Admin</h1>
        <p className="text-[15px] text-muted">
          Across all of Popshot: counts, and crew names. Nothing about the people in them.
        </p>
      </header>
      {overview.result.kind === "loading" && <p className="text-muted">Loading the numbers…</p>}
      {overview.result.kind === "error" && (
        <p role="alert" className="text-warn">
          We couldn&apos;t load the numbers just now.
        </p>
      )}
      {overview.result.kind === "ready" && <OverviewSections overview={overview.result.data} />}
      {groups.result.kind === "ready" && <GroupsSection groups={groups.result.data} />}
    </main>
  );
}

function NotFound() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-col px-5 pt-10 pb-12">
      <h1 className="text-[28px] leading-[1.1] font-extrabold">That page is out of bounds.</h1>
      <p className="mt-3 text-[17px] text-muted">The link may be old, or the page may have moved.</p>
      <Link className={buttonClass("primary", "mt-8 self-start")} href="/">
        Back to Popshot
      </Link>
    </main>
  );
}

function SignInAgain({ onDone }: { onDone: () => void }) {
  const { user } = useSignedIn();
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-4 px-5 pt-10 pb-12">
      <h1 className="text-[28px] leading-tight font-extrabold">Sign in again</h1>
      <p className="text-[17px] text-muted">
        The admin page needs a sign-in from the last 12 hours. Sign in with the same Google account to carry on.
      </p>
      <button
        type="button"
        className={buttonClass("primary", "self-start")}
        disabled={busy}
        onClick={() => {
          setBusy(true);
          setProblem(null);
          reauthenticate(user)
            .then(onDone)
            .catch(() => {
              setProblem("That didn't finish. Use the same Google account you're signed in with.");
            })
            .finally(() => {
              setBusy(false);
            });
        }}
      >
        Sign in with Google
      </button>
      <p role="alert" className="text-[15px] text-warn empty:hidden">
        {problem}
      </p>
    </main>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  const id = `admin-${title.toLowerCase().replace(/\W+/g, "-")}`;
  return (
    <section aria-labelledby={id} className="flex animate-rise flex-col gap-3">
      <h2 id={id} className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Stat({ label, value, note }: { label: string; value: number; note?: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-2xl border border-line bg-surface p-4">
      <dt className="text-[14px] text-muted">{label}</dt>
      <dd className="text-[28px] leading-none font-extrabold tabular-nums [font-stretch:75%]">{value}</dd>
      {note && <dd className="text-[13px] text-muted">{note}</dd>}
    </div>
  );
}

/** A table that scrolls sideways inside its card on narrow screens, never the page. */
function Table({ label, head, rows }: { label: string; head: string[]; rows: (string | number)[][] }) {
  return (
    <div className="overflow-x-auto rounded-2xl border border-line bg-surface">
      <table aria-label={label} className="w-full text-left text-[14px] tabular-nums">
        <thead>
          <tr className="border-b border-line text-muted">
            {head.map((h) => (
              <th key={h} scope="col" className="px-3 py-2 font-bold whitespace-nowrap first:pl-4">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={String(row[0]) + String(row[1])} className="border-b border-line last:border-b-0">
              {row.map((cell, i) => (
                <td key={i} className="px-3 py-2 whitespace-nowrap first:pl-4 first:font-bold">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OverviewSections({ overview }: { overview: Overview }) {
  const t = overview.totals;
  const now = new Date();
  return (
    <>
      <Section title="Right now">
        <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="People" value={t.users} note={`${String(t.new_users_7d)} new this week`} />
          <Stat label="Active, 7 days" value={t.active_users_7d} note={`${String(t.active_users_30d)} in 30 days`} />
          <Stat label="Crews" value={t.live_groups} note={`${String(t.deleted_groups)} deleted`} />
          <Stat label="Games" value={t.games} note={`${String(t.games_30d)} in 30 days`} />
          <Stat label="Notifications on" value={t.push_users} note={`${share(t.push_users, t.users)} of people`} />
          <Stat label="Level set" value={t.level_set} note={`${share(t.level_set, t.users)} of people`} />
        </dl>
      </Section>
      <Section title="Each week">
        <Table
          label="Each week, newest first"
          head={["Week of", "Active", "New", "Crews", "Games", "Nights", "Answers"]}
          rows={[...overview.weeks]
            .reverse()
            .map((w) => [
              shortDate(w.week_start),
              w.active_users,
              w.new_users,
              w.active_crews,
              w.games,
              w.nights,
              w.answers,
            ])}
        />
      </Section>
      <Section title="Coming back">
        <p className="-mt-1 text-[14px] text-muted">
          Of the people who signed up each week, how many used Popshot 1 to 4 weeks later.
        </p>
        <Table
          label="Coming back, by signup week"
          head={["Signed up", "People", "Week 1", "Week 2", "Week 3", "Week 4"]}
          rows={[...overview.retention].reverse().map((c) => {
            const reached = reachedWeeks(c.cohort_week, now);
            const cells = [c.week_1, c.week_2, c.week_3, c.week_4].map((n, i) =>
              i < reached ? share(n, c.signed_up) : "·",
            );
            return [shortDate(c.cohort_week), c.signed_up, ...cells];
          })}
        />
      </Section>
    </>
  );
}

function GroupsSection({ groups }: { groups: AdminGroup[] }) {
  return (
    <Section title={`Crews (${String(groups.length)})`}>
      {groups.length === 0 ? (
        <p className="text-muted">No crews yet.</p>
      ) : (
        <ul
          aria-label="Crews, most recently active first"
          className="flex flex-col rounded-2xl border border-line bg-surface"
        >
          {groups.map((g) => (
            <li key={g.id} className="flex flex-col gap-0.5 border-b border-line px-4 py-3 last:border-b-0">
              <span className="truncate font-bold">{g.name}</span>
              <span className="text-[14px] text-muted tabular-nums">{crewLine(g)}</span>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function crewLine(g: AdminGroup): string {
  const games = g.last_game_at
    ? `${plural(g.games, "game")}, ${String(g.games_30d)} in 30 days · last ${shortDate(g.last_game_at)}`
    : "no games yet";
  const nights = g.upcoming_nights > 0 ? ` · ${plural(g.upcoming_nights, "night")} ahead` : "";
  return `${plural(g.members, "member")} · ${games}${nights} · started ${shortDate(g.created_at)}`;
}

function plural(n: number, word: string): string {
  return `${String(n)} ${word}${n === 1 ? "" : "s"}`;
}
