"use client";

import Link from "next/link";
import type { ReactNode } from "react";

import type { GroupSummary } from "@/lib/groups";

import { GroupSwitcher } from "./group-switcher";
import { useApiGet } from "./use-api";
import { useCurrentGroup } from "./use-current-group";
import { buttonClass } from "./ui/button";

// A page about one group at a time (Games, Crew): title, group switcher, then content for
// the chosen group. Groups you're still waiting to join aren't offered.
export function GroupScoped({
  title,
  children,
}: {
  title: string;
  children: (group: GroupSummary) => ReactNode;
}) {
  const { result, reload } = useApiGet<GroupSummary[]>("/v1/groups");
  const groups = result.kind === "ready" ? result.data.filter((g) => g.my_status === "active") : [];
  const { current, choose } = useCurrentGroup(groups);

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-5 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <h1 className="text-[32px] leading-tight font-extrabold tracking-[-0.02em] [font-stretch:110%]">{title}</h1>

      {result.kind === "loading" && <p className="text-muted">Loading…</p>}

      {result.kind === "error" && (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-2xl border border-line bg-surface p-5">
          <p>We couldn&apos;t load your groups just now.</p>
          <button type="button" className={buttonClass("quiet")} onClick={reload}>
            Try again
          </button>
        </div>
      )}

      {result.kind === "ready" && !current && (
        <section className="flex flex-col items-start gap-3 rounded-2xl border border-line bg-surface p-5">
          <p className="text-[17px]">You&apos;re not in a group yet. Start one or ask your crew&apos;s lead for an invite.</p>
          <Link href="/" className={buttonClass("primary")}>
            Go to your groups
          </Link>
        </section>
      )}

      {current && (
        <>
          {groups.length > 1 ? (
            <GroupSwitcher groups={groups} current={current} onChange={choose} />
          ) : (
            <p className="text-[17px] font-bold">{current.name}</p>
          )}
          {children(current)}
        </>
      )}
    </main>
  );
}
