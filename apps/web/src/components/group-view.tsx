"use client";

import Link from "next/link";

import { describeRules, ROLE_LABEL, type GroupDetail, type Member } from "@/lib/groups";

import { AppHeader } from "./app-header";
import { useSignedIn } from "./auth";
import { useApiGet } from "./use-api";
import { Avatar } from "./ui/avatar";
import { buttonClass } from "./ui/button";
import { BackIcon } from "./ui/icons";

export function GroupView({ groupId }: { groupId: string }) {
  const { result, reload } = useApiGet<GroupDetail>(`/v1/groups/${groupId}`);

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col gap-5 px-5 pt-12 pb-9">
      <AppHeader />
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
          <p className="text-muted">
            It may have been deleted, or you&apos;re not in it. Ask its lead for an invite.
          </p>
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
  const { me } = useSignedIn();
  const active = group.members.filter((m) => m.status === "active");
  const waiting = group.members.filter((m) => m.status === "pending");

  return (
    <>
      <section className="flex animate-rise flex-col gap-1">
        <h1 className="text-[32px] leading-[1.08] font-extrabold tracking-[-0.02em] break-words [font-stretch:110%]">
          {group.name}
        </h1>
        <p className="text-[15px] text-muted">{describeRules(group)}</p>
      </section>

      {group.my_status === "pending" ? (
        <section className="animate-rise rounded-2xl border border-line bg-surface p-5">
          <h2 className="text-[17px] font-bold">Waiting for approval</h2>
          <p className="mt-1 text-muted">
            The group&apos;s lead will let you in. You&apos;ll see the members and games once they do.
          </p>
        </section>
      ) : (
        <>
          <section aria-labelledby="members-heading" className="flex animate-rise flex-col gap-2 [animation-delay:60ms]">
            <h2 id="members-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
              Members · {active.length}
            </h2>
            <ul className="overflow-hidden rounded-2xl border border-line bg-surface">
              {active.map((member) => (
                <MemberRow key={member.user_id} member={member} isMe={member.user_id === me?.id} />
              ))}
            </ul>
          </section>

          {waiting.length > 0 && (
            <section aria-labelledby="waiting-heading" className="flex animate-rise flex-col gap-2 [animation-delay:120ms]">
              <h2 id="waiting-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
                Waiting for approval · {waiting.length}
              </h2>
              <ul className="overflow-hidden rounded-2xl border border-line bg-surface">
                {waiting.map((member) => (
                  <MemberRow key={member.user_id} member={member} isMe={false} />
                ))}
              </ul>
            </section>
          )}

          <section className="animate-rise rounded-2xl border border-dashed border-line p-5 text-muted [animation-delay:180ms]">
            Invites come next: you&apos;ll share a single-use link, and approve who joins.
          </section>
        </>
      )}
    </>
  );
}

function MemberRow({ member, isMe }: { member: Member; isMe: boolean }) {
  return (
    <li className="flex min-h-16 items-center gap-3 border-b border-line px-4 py-3 last:border-b-0">
      <Avatar name={member.display_name} tone={member.role === "lead" ? "ball" : "chip"} />
      <span className="min-w-0 grow truncate text-[17px] font-bold">
        {member.display_name}
        {isMe && <span className="font-normal text-muted"> (you)</span>}
      </span>
      {member.status === "pending" ? (
        <span className="text-[13px] font-bold text-muted">Asked to join</span>
      ) : (
        member.role !== "member" && (
          <span className="rounded-full bg-chip px-2.5 py-1 text-[13px] font-bold">
            {ROLE_LABEL[member.role]}
          </span>
        )
      )}
    </li>
  );
}
