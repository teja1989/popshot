"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { ROLE_LABEL, type GroupDetail, type GroupSummary } from "@/lib/groups";

import { AppHeader } from "./app-header";
import { useSignedIn } from "./auth";
import { CreateGroupDialog } from "./create-group-dialog";
import { useApiGet } from "./use-api";
import { Avatar } from "./ui/avatar";
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
  const name = me?.display_name ?? null;

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col gap-5 px-5 pt-12 pb-9">
      <AppHeader />

      <section className="flex animate-rise items-center gap-4 rounded-2xl border border-line bg-surface p-4">
        <Avatar name={name} size="lg" />
        <div className="min-w-0">
          <h1 className="truncate text-[26px] leading-tight font-extrabold tracking-[-0.01em] [font-stretch:110%]">
            {name ? `Hi, ${name}.` : "Hi."}
          </h1>
          {problem ? (
            <p className="text-[15px] text-warn">{problem}</p>
          ) : (
            <p className="text-[15px] text-muted">You&apos;re signed in.</p>
          )}
        </div>
      </section>

      <section aria-labelledby="groups-heading" className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
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
                <Link
                  href={`/groups/${group.id}`}
                  className="flex min-h-16 items-center gap-3 rounded-2xl border border-line bg-surface p-4 text-ink no-underline transition-transform duration-150 ease-court hover:-translate-y-px"
                >
                  <Avatar name={group.name} tone={group.my_role === "lead" ? "ball" : "chip"} />
                  <span className="flex min-w-0 grow flex-col">
                    <span className="truncate text-[17px] font-bold">{group.name}</span>
                    <span className="text-[14px] text-muted">
                      {group.my_status === "pending"
                        ? "Waiting for approval"
                        : `${ROLE_LABEL[group.my_role]} · ${String(group.member_count ?? 0)} ${group.member_count === 1 ? "member" : "members"}`}
                    </span>
                  </span>
                  <ChevronIcon />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
