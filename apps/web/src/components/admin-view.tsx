"use client";

import Link from "next/link";
import { useState } from "react";

import { reachedWeeks, share, shortDate, type AdminGroup, type Overview, type PeopleResults } from "@/lib/admin";

import { AdminGate, AdminMain, Section, Stat, Table } from "./admin-ui";
import { Avatar } from "./ui/avatar";
import { useApiGet } from "./use-api";

/**
 * App-wide numbers for the owner. The API returns 404 to anyone who isn't an admin (shown
 * here as a plain "not found"), and 403 when the admin's sign-in is over 12 hours old.
 */
export function AdminView() {
  const overview = useApiGet<Overview>("/v1/admin/overview");
  const groups = useApiGet<AdminGroup[]>("/v1/admin/groups");
  const status = overview.result.kind === "error" ? overview.result.status : null;

  return (
    <AdminGate
      status={status}
      onSignedIn={() => {
        overview.reload();
        groups.reload();
      }}
    >
      <AdminMain>
        <header className="flex animate-rise flex-col gap-1">
          <h1 className="text-title-lg leading-tight font-extrabold font-display">Admin</h1>
          <p className="text-body text-muted">
            Across all of Popshot. Find a person or open a crew to help with an issue.
          </p>
          <div className="flex flex-wrap gap-x-5">
            <Link href="/admin/funnel" className="text-body font-bold text-primary">
              See the funnel →
            </Link>
            <Link href="/admin/features" className="text-body font-bold text-primary">
              Features and plans →
            </Link>
            <Link href="/admin/learn" className="text-body font-bold text-primary">
              Learn shots →
            </Link>
          </div>
        </header>
        {overview.result.kind === "loading" && <p className="text-muted">Loading the numbers…</p>}
        {overview.result.kind === "error" && (
          <p role="alert" className="text-warn">
            We couldn&apos;t load the numbers just now.
          </p>
        )}
        {overview.result.kind === "ready" && <OverviewSections overview={overview.result.data} />}
        <PeopleSearch />
        {groups.result.kind === "ready" && <GroupsSection groups={groups.result.data} />}
      </AdminMain>
    </AdminGate>
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
          head={["Week of", "Active", "New", "Crews", "Games", "Meetups", "Answers"]}
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
        <p className="-mt-1 text-small text-muted">
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
              <Link href={`/admin/crews/${g.id}`} className="truncate font-bold text-ink">
                {g.name}
              </Link>
              <span className="text-small text-muted tabular-nums">{crewLine(g)}</span>
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
  const nights = g.upcoming_nights > 0 ? ` · ${plural(g.upcoming_nights, "meetup")} ahead` : "";
  return `${plural(g.members, "member")} · ${games}${nights} · started ${shortDate(g.created_at)}`;
}

export function plural(n: number, word: string): string {
  return `${String(n)} ${word}${n === 1 ? "" : "s"}`;
}

/** Find someone by any part of their name, their id, or their exact email. */
function PeopleSearch() {
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState<string | null>(null);
  return (
    <Section title="Find a person">
      <form
        role="search"
        className="flex gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          const q = draft.trim();
          setQuery(q.length >= 2 ? q : null);
        }}
      >
        <label htmlFor="admin-people-q" className="sr-only">
          Name, email or id
        </label>
        <input
          id="admin-people-q"
          type="search"
          value={draft}
          onChange={(event) => {
            setDraft(event.target.value);
          }}
          placeholder="Name, email or id"
          minLength={2}
          maxLength={100}
          autoComplete="off"
          className="min-h-12 min-w-0 grow rounded-xl border border-line bg-surface px-4 text-field"
        />
        <button type="submit" className="min-h-12 shrink-0 rounded-xl bg-primary px-5 font-bold text-on-primary">
          Find
        </button>
      </form>
      {query && <PeopleResultsList query={query} />}
    </Section>
  );
}

function PeopleResultsList({ query }: { query: string }) {
  const { result } = useApiGet<PeopleResults>(`/v1/admin/people?q=${encodeURIComponent(query)}`);
  if (result.kind === "loading") {
    return <p className="text-muted">Looking…</p>;
  }
  if (result.kind === "error") {
    return (
      <p role="alert" className="text-warn">
        That search didn&apos;t work just now.
      </p>
    );
  }
  const { people, email_search } = result.data;
  if (people.length === 0) {
    return (
      <p className="text-muted">
        {email_search ? "Nobody matches that." : "Email search isn't available here. Try a name."}
      </p>
    );
  }
  return (
    <ul aria-label="People found" className="flex flex-col rounded-2xl border border-line bg-surface">
      {people.map((p) => (
        <li key={p.id} className="border-b border-line last:border-b-0">
          <Link href={`/admin/people/${p.id}`} className="flex items-center gap-3 px-4 py-3 text-ink no-underline">
            <Avatar name={p.display_name} photoUrl={p.avatar_url} size="sm" />
            <span className="flex min-w-0 flex-col">
              <span className="truncate font-bold">{p.display_name}</span>
              <span className="text-small text-muted">
                {plural(p.groups, "crew")} · joined {shortDate(p.created_at)} · last active{" "}
                {p.last_active ? shortDate(p.last_active) : "never"}
              </span>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
