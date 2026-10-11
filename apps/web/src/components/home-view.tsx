"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo } from "react";

import { points, type MyRating } from "@/lib/board";
import { ROLE_LABEL, type GroupDetail, type GroupSummary } from "@/lib/groups";
import { firstName, greetingFor } from "@/lib/people";

import { useSignedIn } from "./auth";
import { CreateGroupDialog } from "./create-group-dialog";
import { DeletedGroups } from "./deleted-groups";
import { JoinByLinkSheet } from "./join-by-link-sheet";
import { useApiGet } from "./use-api";
import { Avatar, AvatarStack } from "./ui/avatar";
import { buttonClass } from "./ui/button";
import { CourtArt } from "./ui/court-art";
import { CourtPattern } from "./ui/court-pattern";
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
  // Your crew points in the group you've played most in.
  const ratings = useApiGet<MyRating[]>("/v1/me/ratings");
  const top = ratings.result.kind === "ready" ? ratings.result.data[0] : undefined;
  const ratingsCount = ratings.result.kind === "ready" ? ratings.result.data.length : 0;

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 px-5 pt-6 pb-12 lg:max-w-5xl lg:px-8 lg:pt-10">

      <section className="relative isolate animate-rise overflow-hidden rounded-[28px] bg-hero p-6 text-on-hero lg:p-9">
        <CourtPattern />
        <div className="flex items-center gap-4">
          <Avatar
            name={me?.display_name}
            photoUrl={me?.avatar_url}
            size="lg"
            className="ring-4 ring-hero-line"
          />
          <div className="min-w-0">
            <p className="text-[14px] font-bold text-on-hero-muted">{today}</p>
            <h1 className="text-[30px] leading-[1.05] font-extrabold tracking-[-0.02em] break-words [font-stretch:112%] lg:text-[42px]">
              {greeting}
              {name ? (
                <>
                  , <span className="text-ball">{name}</span>.
                </>
              ) : (
                "."
              )}
            </h1>
            <p className="mt-1 text-[16px] text-on-hero-muted">Play, laugh, stay active. Popshot keeps the score.</p>
            {problem && <p className="text-[15px] font-bold text-ball">{problem}</p>}
          </div>
        </div>
        <dl className="mt-7 grid max-w-lg grid-cols-3 gap-4 border-t border-hero-line pt-5">
          <HeroStat
            label="Groups"
            value={result.kind === "ready" ? String(result.data.filter((g) => g.my_status === "active").length) : "–"}
          />
          <HeroStat
            label="Games played"
            value={result.kind === "ready" ? String(result.data.reduce((sum, g) => sum + (g.my_games ?? 0), 0)) : "–"}
          />
          <HeroStat
            label="Crew points"
            value={top ? points(top.rating) : "–"}
            note={top ? (ratingsCount > 1 ? top.group_name : undefined) : "After your first game"}
          />
        </dl>
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start">
        <section aria-labelledby="groups-heading" className="flex flex-col gap-3">
          <div className="flex min-h-11 items-center justify-between">
            <h2 id="groups-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
              Your groups
            </h2>
            {result.kind === "ready" && result.data.length > 0 && (
              <JoinByLinkSheet
                trigger={
                  <button type="button" className="min-h-11 cursor-pointer px-1 text-[15px] font-bold text-primary">
                    Have an invite link?
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
                No groups yet. Got an invite link from your crew? Join with it. Or start a group
                for the people you play with.
              </p>
              <div className="flex flex-wrap gap-2">
                <JoinByLinkSheet
                  trigger={
                    <button type="button" className={buttonClass("primary")}>
                      Join with an invite link
                    </button>
                  }
                />
                <CreateGroupDialog
                  onCreated={openGroup}
                  trigger={
                    <button type="button" className={buttonClass("quiet")}>
                      <PlusIcon />
                      Start a group
                    </button>
                  }
                />
              </div>
            </div>
          )}

          {result.kind === "ready" && result.data.length > 0 && (
            <ul className="grid gap-3 sm:grid-cols-2">
              {result.data.map((group, index) => (
                <li key={group.id} className={`animate-rise ${STAGGER[index] ?? ""}`}>
                  <GroupCard group={group} />
                </li>
              ))}
              <li className="animate-rise">
                <CreateGroupDialog
                  onCreated={openGroup}
                  trigger={
                    <button
                      type="button"
                      className="flex h-full min-h-40 w-full cursor-pointer flex-col items-center justify-center gap-2 rounded-3xl border-2 border-dashed border-line text-[16px] font-bold text-muted transition-colors duration-150 hover:border-primary hover:text-primary"
                    >
                      <span className="flex size-11 items-center justify-center rounded-full bg-chip text-primary">
                        <PlusIcon />
                      </span>
                      Start a group
                    </button>
                  }
                />
              </li>
            </ul>
          )}
          <DeletedGroups />
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
      className="group flex h-full flex-col overflow-hidden rounded-3xl border border-line bg-surface text-ink no-underline transition-[translate,box-shadow] duration-200 ease-court hover:-translate-y-0.5 hover:shadow-[0_18px_40px_-24px_rgb(15_27_38/0.45)]"
    >
      <span className="relative isolate block h-20 overflow-hidden bg-hero">
        <CourtPattern />
        <span
          aria-hidden="true"
          className={`absolute top-1/2 size-4 -translate-y-1/2 rounded-full bg-ball transition-transform duration-500 ease-court group-hover:-translate-x-6 ${BALL_SPOTS[ballSpot(group.id)] ?? ""}`}
        />
      </span>
      <span className="flex grow flex-col gap-3 p-4">
        <span className="flex items-start justify-between gap-3">
          <span className="flex min-w-0 flex-col gap-0.5">
            <span className="truncate text-[19px] font-extrabold [font-stretch:105%]">{group.name}</span>
            <span className="text-[14px] text-muted">
              {group.my_status === "pending"
                ? "Waiting for approval"
                : `${ROLE_LABEL[group.my_role]} · ${String(count)} ${count === 1 ? "member" : "members"} · ${String(group.games_logged ?? 0)} ${group.games_logged === 1 ? "game" : "games"}`}
            </span>
          </span>
          <ChevronIcon />
        </span>
        {group.my_status === "active" && <AvatarStack people={group.member_preview} total={count} />}
      </span>
    </Link>
  );
}

// Where the ball sits on a group's banner: fixed per group, so each tile looks its own.
const BALL_SPOTS = ["left-[22%]", "left-[38%]", "left-[62%]", "left-[78%]"];

function ballSpot(id: string): number {
  let hash = 0;
  for (const ch of id) {
    hash = (hash * 31 + ch.charCodeAt(0)) % 997;
  }
  return hash % BALL_SPOTS.length;
}

function HeroStat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-[13px] font-bold text-on-hero-muted">{label}</dt>
      <dd className="flex flex-col gap-1">
        <span className="text-[34px] leading-none font-extrabold [font-stretch:75%] lg:text-[40px]">{value}</span>
        {note && <span className="text-[12px] text-on-hero-muted">{note}</span>}
      </dd>
    </div>
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
        {["Win rate", "Crew points", "Streak"].map((label) => (
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
        Your win rate, streaks and form arrive with the stats update next. Crew points are live on
        the Board now.
      </p>
    </aside>
  );
}
