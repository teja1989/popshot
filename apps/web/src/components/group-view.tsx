"use client";

import Link from "next/link";
import { useEffect } from "react";

import { apiPatch } from "@/lib/api-client";
import { describeRules, type GroupDetail } from "@/lib/groups";
import { browserTimeZone, shouldFillTimeZone } from "@/lib/time-zone";

import { useSignedIn } from "./auth";
import { CrewProfileSummary } from "./crew-profile-summary";
import { PlayNightsSection } from "./play-nights-section";
import { useApiGet } from "./use-api";
import { AvatarStack } from "./ui/avatar";
import { buttonClass } from "./ui/button";
import { BackIcon, ChevronIcon, PlusIcon } from "./ui/icons";

// Crews whose time zone this tab has already tried to fill in, so it's sent once.
const zoneSent = new Set<string>();

export function GroupView({ groupId }: { groupId: string }) {
  const { user } = useSignedIn();
  const { result, reload, replace } = useApiGet<GroupDetail>(`/v1/groups/${groupId}`);
  const group = result.kind === "ready" ? result.data : null;

  // Crews made before time zones were kept get the zone of their lead's device, once.
  useEffect(() => {
    if (!group || zoneSent.has(group.id)) return;
    const zone = browserTimeZone();
    if (!shouldFillTimeZone(group, zone)) return;
    zoneSent.add(group.id);
    apiPatch<GroupDetail>(user, `/v1/groups/${group.id}`, { time_zone: zone }).then(replace, () => {
      // Nothing to show: it's tried again on the next visit.
      zoneSent.delete(group.id);
    });
  }, [group, user, replace]);

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-5 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <Link
        href="/"
        className="-ml-1 flex min-h-11 items-center gap-1.5 self-start text-body font-bold text-primary no-underline"
      >
        <BackIcon />
        Your groups
      </Link>

      {result.kind === "loading" && <p className="text-muted">Loading the group…</p>}

      {result.kind === "error" && result.status === 404 && (
        <section className="flex flex-col gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-5">
          <h1 className="text-title-lg font-extrabold font-display">We couldn&apos;t find that group.</h1>
          <p className="text-muted">It may have been deleted, or you&apos;re not in it. Ask its lead for an invite.</p>
        </section>
      )}

      {result.kind === "error" && result.status !== 404 && (
        <div
          role="alert"
          className="flex flex-col items-start gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-5"
        >
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
        <h1 className="text-display-sm leading-[1.08] font-extrabold tracking-[-0.02em] break-words font-display">
          {group.name}
        </h1>
        <p className="text-body text-muted">{describeRules(group)}</p>
        <div className="mt-2">
          <CrewProfileSummary profile={group} courts={group.courts} />
        </div>
        <Link
          href={`/groups/${group.id}/settings`}
          className={buttonClass("quiet", "mt-2 min-h-11 self-start px-4 text-body")}
        >
          Settings
        </Link>
      </section>

      {group.my_status === "pending" ? (
        <section className="animate-rise rounded-3xl border border-transparent bg-surface shadow-card p-5">
          <h2 className="text-lead font-bold">Waiting for approval</h2>
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
            className="flex min-h-16 animate-rise items-center gap-3 rounded-3xl border border-transparent bg-surface shadow-card px-4 py-3 text-ink no-underline pressable [animation-delay:60ms]"
          >
            <AvatarStack people={active.slice(0, 4)} total={active.length} />
            <span className="flex min-w-0 grow flex-col">
              <span className="text-lead font-bold">Members · {active.length}</span>
              <span className="text-small text-muted">See everyone, guests and invites</span>
            </span>
            {waiting > 0 && (
              <span className="shrink-0 rounded-full bg-ball px-2.5 py-1 text-meta font-bold text-on-ball">
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
