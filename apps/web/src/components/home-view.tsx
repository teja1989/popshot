"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState, type ReactNode } from "react";

import { points, type MyRating } from "@/lib/board";
import { ROLE_LABEL, type GroupDetail, type GroupSummary } from "@/lib/groups";
import { firstName, greetingFor } from "@/lib/people";

import { useSignedIn } from "./auth";
import { CreateGroupDialog } from "./create-group-dialog";
import { CrewPointsInfo } from "./crew-points-info";
import { DeletedGroups } from "./deleted-groups";
import { useHomeRefresh } from "./home-refresh";
import { InstallBanner } from "./install-banner";
import { InviteInbox } from "./invite-inbox";
import { DeletionNotice } from "./your-data-section";
import { YourWeekCard } from "./your-week-card";
import { NextNight } from "./next-night";
import { JoinByLinkSheet } from "./join-by-link-sheet";
import { useApiGet } from "./use-api";
import { useCurrentGroup } from "./use-current-group";
import { Avatar, AvatarStack } from "./ui/avatar";
import { buttonClass } from "./ui/button";
import { CourtArt } from "./ui/court-art";
import { CourtPattern } from "./ui/court-pattern";
import { Fab } from "./ui/fab";
import { ChevronIcon, PlusIcon } from "./ui/icons";

// Written out in full so Tailwind can see them (it doesn't evaluate code).
const STAGGER = [
  "",
  "[animation-delay:60ms]",
  "[animation-delay:120ms]",
  "[animation-delay:180ms]",
  "[animation-delay:240ms]",
  "[animation-delay:300ms]",
];

export function HomeView() {
  const { me, problem } = useSignedIn();
  const router = useRouter();
  const { result, reload } = useApiGet<GroupSummary[]>("/v1/groups");
  // "Log a game" opens in the crew you last played or looked at (as Play does).
  const { current: logIn } = useCurrentGroup(
    result.kind === "ready" ? result.data.filter((g) => g.my_status === "active") : [],
  );
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

  // Asked to refresh (the logo or Home tab, tapped at the top of Home): "Updated." once the
  // groups have come back, for a few seconds.
  const [refreshedFrom, setRefreshedFrom] = useState<typeof result | null>(null);
  const reloadRatings = ratings.reload;
  const refresh = useCallback(() => {
    setRefreshedFrom(result);
    reload();
    reloadRatings();
    setTimeout(() => {
      setRefreshedFrom(null);
    }, 4000);
  }, [result, reload, reloadRatings]);
  useHomeRefresh(refresh);
  const updated = refreshedFrom !== null && result !== refreshedFrom && result.kind === "ready";

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 px-5 pt-6 pb-12 lg:max-w-5xl lg:px-8 lg:pt-10">
      <section className="relative isolate animate-rise overflow-hidden rounded-[28px] bg-hero p-6 text-on-hero lg:p-9">
        <CourtPattern />
        <div className="flex items-center gap-4">
          <Avatar name={me?.display_name} photoUrl={me?.avatar_url} size="lg" className="ring-4 ring-hero-line" />
          <div className="min-w-0">
            <p className="text-small font-bold text-on-hero-muted">{today}</p>
            <h1 className="text-display-sm leading-[1.05] font-extrabold tracking-[-0.02em] break-words font-display lg:text-display">
              {greeting}
              {name ? (
                <>
                  , <span className="text-ball">{name}</span>.
                </>
              ) : (
                "."
              )}
            </h1>
            <p className="mt-1 text-lead text-on-hero-muted">Play, laugh, stay active. Popshot keeps the score.</p>
            {problem && <p className="text-body font-bold text-ball">{problem}</p>}
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
            info={<CrewPointsInfo tone="hero" />}
            value={top ? points(top.rating) : "–"}
            note={top ? (ratingsCount > 1 ? top.group_name : undefined) : "After your first game"}
          />
        </dl>
      </section>

      <DeletionNotice />

      <InviteInbox onJoined={reload} />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-start">
        <section aria-labelledby="groups-heading" className="flex flex-col gap-3">
          {result.kind === "ready" && result.data.some((g) => g.my_status === "active") && (
            <>
              <NextNight />
              <InstallBanner />
            </>
          )}
          <div className="flex min-h-11 items-center justify-between">
            <div className="flex items-baseline gap-2">
              <h2 id="groups-heading" className="text-title-sm font-bold text-ink">
                Your groups
              </h2>
              <p role="status" className="text-meta font-bold text-primary">
                {updated ? "Updated." : ""}
              </p>
            </div>
            {result.kind === "ready" && result.data.length > 0 && (
              <JoinByLinkSheet
                trigger={
                  <button type="button" className="min-h-11 cursor-pointer px-1 text-body font-bold text-primary">
                    Have an invite link?
                  </button>
                }
              />
            )}
          </div>

          {result.kind === "loading" && <p className="text-muted">Loading your groups…</p>}

          {result.kind === "error" && (
            <div
              role="alert"
              className="flex flex-col items-start gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-5"
            >
              <p>We couldn&apos;t load your groups just now.</p>
              <button type="button" className={buttonClass("quiet")} onClick={reload}>
                Try again
              </button>
            </div>
          )}

          {result.kind === "ready" && result.data.length === 0 && (
            <div className="flex animate-rise flex-col gap-4 rounded-3xl border border-transparent bg-surface shadow-card p-5">
              <CourtArt className="w-40" />
              <p className="text-lead leading-relaxed">
                No groups yet. Got an invite link from your crew? Join with it. Or start a group for the people you play
                with.
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
                      className="flex h-full min-h-40 w-full cursor-pointer flex-col items-center justify-center gap-2 rounded-3xl border-2 border-dashed border-line text-lead font-bold text-muted transition-colors duration-150 hover:border-primary hover:text-primary"
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

        <div className="flex flex-col gap-6">
          {result.kind === "ready" && result.data.some((g) => g.my_status === "active") && <YourWeekCard />}
          <StatsPanel top={top} loading={ratings.result.kind === "loading"} groups={ratingsCount} />
        </div>
      </div>
      {logIn && <Fab href={`/groups/${logIn.id}/log`} label="Log a game" />}
    </main>
  );
}

function GroupCard({ group }: { group: GroupSummary }) {
  const count = group.member_count ?? 0;
  return (
    <Link
      href={`/groups/${group.id}`}
      className="group flex h-full flex-col overflow-hidden rounded-3xl border border-transparent bg-surface shadow-card text-ink no-underline pressable"
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
            <span className="truncate text-title-sm font-extrabold font-display">{group.name}</span>
            <span className="text-small text-muted">
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

function HeroStat({ label, value, note, info }: { label: string; value: string; note?: string; info?: ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="-my-2 flex items-center gap-0.5 text-meta font-bold text-on-hero-muted">
        {label}
        {info}
      </dt>
      <dd className="flex flex-col gap-1">
        <span className="text-display-sm leading-none font-extrabold font-numeral lg:text-display">{value}</span>
        {note && <span className="text-meta text-on-hero-muted">{note}</span>}
      </dd>
    </div>
  );
}

function StatsPanel({ top, loading, groups }: { top: MyRating | undefined; loading: boolean; groups: number }) {
  const wins = top ? top.form.filter((r) => r === "W").length : 0;
  return (
    <aside
      aria-labelledby="home-stats-heading"
      className="flex animate-rise flex-col gap-4 rounded-3xl border border-transparent bg-surface shadow-card p-5 [animation-delay:120ms]"
    >
      <h2 id="home-stats-heading" className="text-title-sm font-bold text-ink">
        Your stats{top && groups > 1 ? ` · ${top.group_name}` : ""}
      </h2>
      {!top && !loading && (
        <p className="text-body leading-relaxed text-muted">
          Log your first game and your crew points, form and weekly games show up here.
        </p>
      )}
      {top && (
        <>
          <dl className="grid grid-cols-3 gap-3">
            <PanelStat label="Crew points" value={points(top.rating)} />
            <PanelStat
              label={`Last ${String(top.form.length)}`}
              value={`${String(wins)}–${String(top.form.length - wins)}`}
            />
            <PanelStat
              label="Last 7 days"
              value={String(top.week_games)}
              note={top.week_games === 1 ? "game" : "games"}
            />
          </dl>
          <span
            className="flex flex-wrap gap-1"
            aria-label={`Last ${String(top.form.length)}, newest first: ${top.form.join(" ")}`}
          >
            {top.form.map((r, i) => (
              <span
                key={i}
                aria-hidden="true"
                className={
                  r === "W"
                    ? "flex size-6 items-center justify-center rounded bg-win text-label font-extrabold text-on-win"
                    : "flex size-6 items-center justify-center rounded border border-dashed border-loss text-label font-extrabold text-muted"
                }
              >
                {r}
              </span>
            ))}
          </span>
          <Link href="/you" className="self-start text-body font-bold text-primary">
            See all your stats
          </Link>
        </>
      )}
    </aside>
  );
}

function PanelStat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="flex flex-col gap-1">
      <dt className="text-meta text-muted">{label}</dt>
      <dd className="text-title-lg leading-none font-extrabold tabular-nums font-numeral">
        {value}
        {note && <span className="text-meta font-bold text-muted font-sans"> {note}</span>}
      </dd>
    </div>
  );
}
