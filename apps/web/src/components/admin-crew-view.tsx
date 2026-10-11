"use client";

import Link from "next/link";

import { membership, shortDate, type Crew } from "@/lib/admin";

import { AdminGate, AdminMain, Section, Stat } from "./admin-ui";
import { plural } from "./admin-view";
import { Avatar } from "./ui/avatar";
import { useApiGet } from "./use-api";

/** One crew, for support: its activity and everyone who has been in it. */
export function AdminCrewView({ crewId }: { crewId: string }) {
  const { result, reload } = useApiGet<Crew>(`/v1/admin/groups/${crewId}`);
  return (
    <AdminGate status={result.kind === "error" ? result.status : null} onSignedIn={reload}>
      <AdminMain>
        <Link href="/admin" className="text-[15px] font-bold text-primary">
          ← Admin
        </Link>
        {result.kind === "loading" && <p className="text-muted">Loading…</p>}
        {result.kind === "error" && (
          <p role="alert" className="text-warn">
            We couldn&apos;t load this crew just now.
          </p>
        )}
        {result.kind === "ready" && <CrewDetail crew={result.data} />}
      </AdminMain>
    </AdminGate>
  );
}

function CrewDetail({ crew: c }: { crew: Crew }) {
  return (
    <>
      <header className="flex animate-rise flex-col gap-1">
        <h1 className="text-[28px] leading-tight font-extrabold break-words [font-stretch:110%]">{c.name}</h1>
        <p className="text-[15px] text-muted">
          Started {shortDate(c.created_at)}
          {c.deleted_at ? ` · deleted ${shortDate(c.deleted_at)}` : ""}
        </p>
      </header>
      <Section title="Activity">
        <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat
            label="Members"
            value={c.members}
            note={
              [c.pending ? `${String(c.pending)} asking to join` : "", c.guests ? plural(c.guests, "guest") : ""]
                .filter(Boolean)
                .join(" · ") || undefined
            }
          />
          <Stat
            label="Games"
            value={c.games}
            note={c.last_game_at ? `last ${shortDate(c.last_game_at)}` : "none yet"}
          />
          <Stat label="Nights ahead" value={c.upcoming_nights} />
          <Stat label="Open invites" value={c.open_invites} />
        </dl>
        <p className="text-[13px] text-muted">ID {c.id}</p>
      </Section>
      <Section title="People">
        <ul aria-label="People in this crew" className="flex flex-col rounded-2xl border border-line bg-surface">
          {c.people.map((m) => (
            <li key={m.user_id} className="border-b border-line last:border-b-0">
              <Link
                href={`/admin/people/${m.user_id}`}
                className="flex items-center gap-3 px-4 py-3 text-ink no-underline"
              >
                <Avatar name={m.display_name} photoUrl={m.avatar_url} size="sm" />
                <span className="flex min-w-0 flex-col">
                  <span className="truncate font-bold">{m.display_name}</span>
                  <span className="text-[14px] text-muted">
                    {membership(m)} · {plural(m.games, "game")} · joined {shortDate(m.joined_at)}
                    {m.user_id === c.created_by ? " · started the crew" : ""}
                  </span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </Section>
    </>
  );
}
