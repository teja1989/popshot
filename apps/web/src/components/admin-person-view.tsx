"use client";

import Link from "next/link";

import { membership, shortDate, type Person } from "@/lib/admin";
import { levelLabel } from "@/lib/board";

import { AdminGate, AdminMain, Section, Stat } from "./admin-ui";
import { plural } from "./admin-view";
import { Avatar } from "./ui/avatar";
import { useApiGet } from "./use-api";

/** One person, for support: their account, activity and every crew they've been in. */
export function AdminPersonView({ personId }: { personId: string }) {
  const { result, reload } = useApiGet<Person>(`/v1/admin/people/${personId}`);
  const status = result.kind === "error" ? result.status : null;
  return (
    <AdminGate status={status} onSignedIn={reload}>
      <AdminMain>
        <Link href="/admin" className="text-body font-bold text-primary">
          ← Admin
        </Link>
        {result.kind === "loading" && <p className="text-muted">Loading…</p>}
        {result.kind === "error" && (
          <p role="alert" className="text-warn">
            We couldn&apos;t load this person just now.
          </p>
        )}
        {result.kind === "ready" && <PersonDetail person={result.data} />}
      </AdminMain>
    </AdminGate>
  );
}

function account(p: Person): string {
  if (p.account === "unavailable") {
    return "Email unavailable here";
  }
  if (p.account === "missing" || !p.email) {
    return "No sign-in account found";
  }
  return p.disabled ? `${p.email} · sign-in disabled` : p.email;
}

function PersonDetail({ person: p }: { person: Person }) {
  return (
    <>
      <header className="flex animate-rise items-center gap-4">
        <Avatar name={p.display_name} photoUrl={p.avatar_url} size="lg" />
        <div className="min-w-0">
          <h1 className="truncate text-title-lg leading-tight font-extrabold font-display">{p.display_name}</h1>
          <p className="text-body break-all text-muted">{account(p)}</p>
        </div>
      </header>
      <Section title="Account">
        <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat
            label="Active days, 30"
            value={p.active_days_30}
            note={`last ${p.last_active ? shortDate(p.last_active) : "never"}`}
          />
          <Stat label="Crews" value={p.groups.filter((g) => g.status === "active" && !g.deleted_at).length} />
          <Stat label="Notification devices" value={p.push_devices} />
          <div className="flex flex-col gap-1 rounded-2xl border border-line bg-surface p-4">
            <dt className="text-small text-muted">Joined</dt>
            <dd className="text-title-sm font-extrabold">{shortDate(p.created_at)}</dd>
            <dd className="text-meta text-muted">
              Level: {levelLabel(p.self_level) ?? "not set"}
              {p.last_sign_in ? ` · signed in ${shortDate(p.last_sign_in)}` : ""}
            </dd>
          </div>
        </dl>
        <p className="text-meta text-muted">ID {p.id}</p>
      </Section>
      <Section title="Crews">
        {p.groups.length === 0 ? (
          <p className="text-muted">Not in any crew.</p>
        ) : (
          <ul aria-label="Their crews" className="flex flex-col rounded-2xl border border-line bg-surface">
            {p.groups.map((g) => (
              <li key={g.group_id} className="flex flex-col gap-0.5 border-b border-line px-4 py-3 last:border-b-0">
                <Link href={`/admin/crews/${g.group_id}`} className="truncate font-bold text-ink">
                  {g.name}
                </Link>
                <span className="text-small text-muted">
                  {membership(g)} · {plural(g.games, "game")} · joined {shortDate(g.joined_at)}
                  {g.deleted_at ? ` · crew deleted ${shortDate(g.deleted_at)}` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </>
  );
}
