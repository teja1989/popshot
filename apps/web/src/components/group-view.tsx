"use client";

import Link from "next/link";

import { describeRules, type GroupDetail } from "@/lib/groups";

import { CrewProfileSummary } from "./crew-profile-summary";
import { PlayNightsSection } from "./play-nights-section";
import { useApiGet } from "./use-api";
import { AvatarStack } from "./ui/avatar";
import { buttonClass } from "./ui/button";
import { BackIcon, ChevronIcon, PlusIcon } from "./ui/icons";

export function GroupView({ groupId }: { groupId: string }) {
  const { result, reload } = useApiGet<GroupDetail>(`/v1/groups/${groupId}`);

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-5 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <Link
        href="/"
        className="-ml-1 flex min-h-11 items-center gap-1.5 self-start text-[15px] font-bold text-primary no-underline"
      >
        <BackIcon />
        Your groups
      </Link>

      {result.kind === "loading" && <p className="text-muted">Loading the group…</p>}

      {result.kind === "error" && result.status === 404 && (
        <section className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-5">
          <h1 className="text-[26px] font-extrabold [font-stretch:108%]">We couldn&apos;t find that group.</h1>
          <p className="text-muted">It may have been deleted, or you&apos;re not in it. Ask its lead for an invite.</p>
        </section>
      )}

      {result.kind === "error" && result.status !== 404 && (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-2xl border border-line bg-surface p-5">
          <p>We couldn&apos;t load this group just now.</p>
          <button type="button" className={buttonClass("quiet")} onClick={reload}>
            Try again
          </button>
        </div>
      )}

      {result.kind === "ready" && <Group group={result.data} />}
    </main>
  );
}

function Group({ group }: { group: GroupDetail }) {
  const active = group.members.filter((m) => m.status === "active");
  const waiting = group.members.filter((m) => m.status === "pending").length;

  return (
    <>
      <section className="flex animate-rise flex-col gap-1">
        <h1 className="text-[32px] leading-[1.08] font-extrabold tracking-[-0.02em] break-words [font-stretch:110%]">
          {group.name}
        </h1>
        <p className="text-[15px] text-muted">{describeRules(group)}</p>
        <div className="mt-2">
          <CrewProfileSummary profile={group} />
        </div>
        <Link
          href={`/groups/${group.id}/settings`}
          className={buttonClass("quiet", "mt-2 min-h-11 self-start px-4 text-[15px]")}
        >
          Settings
        </Link>
      </section>

      {group.my_status === "pending" ? (
        <section className="animate-rise rounded-2xl border border-line bg-surface p-5">
          <h2 className="text-[17px] font-bold">Waiting for approval</h2>
          <p className="mt-1 text-muted">
            The group&apos;s lead or a co-lead will let you in. You&apos;ll see the members and games once they do.
          </p>
        </section>
      ) : (
        <>
          <Link href={`/groups/${group.id}/log`} className={buttonClass("action", "h-14 animate-rise")}>
            <PlusIcon />
            Log a game
          </Link>

          <PlayNightsSection groupId={group.id} />

          <Link
            href={`/groups/${group.id}/members`}
            aria-label={`Members · ${String(active.length)}${waiting > 0 ? `, ${String(waiting)} asking to join` : ""}`}
            className="flex min-h-16 animate-rise items-center gap-3 rounded-2xl border border-line bg-surface px-4 py-3 text-ink no-underline [animation-delay:60ms]"
          >
            <AvatarStack people={active.slice(0, 4)} total={active.length} />
            <span className="flex min-w-0 grow flex-col">
              <span className="text-[17px] font-bold">Members · {active.length}</span>
              <span className="text-[14px] text-muted">See everyone, guests and invites</span>
            </span>
            {waiting > 0 && (
              <span className="shrink-0 rounded-full bg-ball px-2.5 py-1 text-[13px] font-bold text-on-ball">
                {waiting} asking to join
              </span>
            )}
            <ChevronIcon />
          </Link>
        </>
      )}
    </>
  );
}
