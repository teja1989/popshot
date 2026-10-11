"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { ROLE_LABEL, type GroupDetail, type GroupSummary } from "@/lib/groups";
import { firstName, greetingFor } from "@/lib/people";

import { AppHeader } from "./app-header";
import { useSignedIn } from "./auth";
import { CreateGroupDialog } from "./create-group-dialog";
import { useApiGet } from "./use-api";
import { Avatar, AvatarStack } from "./ui/avatar";
import { buttonClass } from "./ui/button";
import { CourtArt } from "./ui/court-art";
import { ChevronIcon, PlusIcon } from "./ui/icons";

// Written out in full so Tailwind can see them (it doesn't evaluate code).
const STAGGER = [
  "",
  "[animation-delay:50ms]",
  "[animation-delay:100ms]",
  "[animation-delay:150ms]",
  "[animation-delay:200ms]",
  "[animation-delay:250ms]",
];

export function HomeView() {
  const { me, problem } = useSignedIn();
  const router = useRouter();
  const { result, reload } = useApiGet<GroupSummary[]>("/v1/groups");
  const openGroup = (group: GroupDetail) => {
    router.push(`/groups/${group.id}`);
  };

  // Local time: rendered in the browser only, so no server/client mismatch.
  const { greeting, today } = useMemo(() => {
    const now = new Date();
    return {
      greeting: greetingFor(now.getHours()),
      today: new Intl.DateTimeFormat(undefined, {
        weekday: "long",
        day: "numeric",
        month: "long",
      }).format(now),
    };
  }, []);
  const name = firstName(me?.display_name);

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col gap-6 px-5 pt-10 pb-12 lg:max-w-5xl lg:px-8">
      <AppHeader />

      <section className="relative isolate animate-rise overflow-hidden rounded-3xl border border-line bg-surface p-5 lg:p-7">
        <CourtMotif />
        <div className="flex items-center gap-4">
          <Avatar name={me?.display_name} photoUrl={me?.avatar_url} size="lg" />
          <div className="min-w-0">
            <p className="text-[14px] font-bold text-muted">{today}</p>
            <h1 className="text-[28px] leading-tight font-extrabold tracking-[-0.01em] break-words [font-stretch:110%] lg:text-[34px]">
              {name ? `${greeting}, ${name}.` : `${greeting}.`}
            </h1>
            {problem && <p className="text-[15px] text-warn">{problem}</p>}
          </div>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start">
        <section aria-labelledby="groups-heading" className="flex flex-col gap-3">
          <div className="flex min-h-11 items-center justify-between">
            <h2 id="groups-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
              Your groups
            </h2>
            {result.kind === "ready" && result.data.length > 0 && (
              <CreateGroupDialog
                onCreated={openGroup}
                trigger={
                  <button type="button" className={buttonClass("quiet", "min-h-11 px-4 text-[15px]")}>
                    <PlusIcon />
                    Start a group
                  </button>
                }
              />
            )}
          </div>

          {result.kind === "loading" && <p className="text-muted">Loading your groups…</p>}

          {result.kind === "error" && (
            <div role="alert" className="flex flex-col items-start gap-3 rounded-2xl border border-line bg-surface p-5">
              <p>We couldn&apos;t load your groups just now.</p>
              <button type="button" className={buttonClass("quiet")} onClick={reload}>
                Try again
              </button>
            </div>
          )}

          {result.kind === "ready" && result.data.length === 0 && (
            <div className="flex animate-rise flex-col gap-4 rounded-2xl border border-line bg-surface p-5">
              <CourtArt className="w-40" />
              <p className="text-[17px] leading-relaxed">
                No groups yet. Start one for the people you play with, then invite them.
              </p>
              <CreateGroupDialog
                onCreated={openGroup}
                trigger={
                  <button type="button" className={buttonClass("primary", "self-start")}>
                    <PlusIcon />
                    Start a group
                  </button>
                }
              />
            </div>
          )}

          {result.kind === "ready" && result.data.length > 0 && (
            <ul className="flex flex-col gap-2">
              {result.data.map((group, index) => (
                <li key={group.id} className={`animate-rise ${STAGGER[index] ?? ""}`}>
                  <GroupCard group={group} />
                </li>
              ))}
            </ul>
          )}
        </section>

        <StatsPanel />
      </div>
    </main>
  );
}

function GroupCard({ group }: { group: GroupSummary }) {
  const count = group.member_count ?? 0;
  return (
    <Link
      href={`/groups/${group.id}`}
      className="flex min-h-20 items-center gap-4 rounded-2xl border border-line bg-surface p-4 text-ink no-underline transition-[translate,border-color] duration-150 ease-court hover:-translate-y-px hover:border-primary"
    >
      <span className="flex min-w-0 grow flex-col gap-0.5">
        <span className="truncate text-[18px] font-bold">{group.name}</span>
        <span className="text-[14px] text-muted">
          {group.my_status === "pending"
            ? "Waiting for approval"
            : `${ROLE_LABEL[group.my_role]} · ${String(count)} ${count === 1 ? "member" : "members"}`}
        </span>
      </span>
      {group.my_status === "active" && (
        <AvatarStack people={group.member_preview} total={count} />
      )}
      <ChevronIcon />
    </Link>
  );
}

function StatsPanel() {
  return (
    <aside
      aria-labelledby="stats-heading"
      className="flex animate-rise flex-col gap-4 rounded-3xl border border-line bg-surface p-5 [animation-delay:120ms]"
    >
      <h2 id="stats-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
        Your stats
      </h2>
      <dl className="grid grid-cols-3 gap-3">
        {["Win rate", "Crew rating", "Streak"].map((label) => (
          <div key={label} className="flex flex-col gap-1">
            <dt className="text-[13px] text-muted">{label}</dt>
            <dd className="text-[28px] leading-none font-extrabold text-loss [font-stretch:75%]">
              <span aria-hidden="true">–</span>
              <span className="sr-only">Not yet</span>
            </dd>
          </div>
        ))}
      </dl>
      <svg viewBox="0 0 300 64" className="w-full" aria-hidden="true">
        <path
          d="M2 52 C 40 50, 60 30, 95 36 S 150 18, 190 26 S 250 8, 298 14"
          fill="none"
          strokeWidth="2.5"
          strokeDasharray="5 7"
          strokeLinecap="round"
          className="stroke-line"
        />
      </svg>
      <p className="text-[15px] leading-relaxed text-muted">
        Your stats start with your first confirmed game: form, partners, rivals and how
        you&apos;re trending.
      </p>
    </aside>
  );
}

// Faint court lines at the greeting's right edge, on screens wide enough that they never sit
// behind the text. Decorative.
function CourtMotif() {
  return (
    <svg
      viewBox="0 0 220 140"
      aria-hidden="true"
      className="pointer-events-none absolute top-1/2 -right-6 -z-10 hidden w-72 -translate-y-1/2 stroke-line opacity-60 sm:block"
    >
      <rect x="4" y="4" width="212" height="132" rx="6" fill="none" strokeWidth="2" />
      <path d="M110 4v132M74 4v132M146 4v132M4 70h70M146 70h70" fill="none" strokeWidth="2" />
    </svg>
  );
}
