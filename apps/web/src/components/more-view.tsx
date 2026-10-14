"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState, type ReactNode } from "react";

import { featureOn } from "@/lib/features";
import type { GroupSummary } from "@/lib/groups";
import { availableItems, isNew, MORE_ITEMS, searchItems, SECTION_LABEL, SECTIONS, type MoreItem } from "@/lib/more";

import { useAuth } from "./auth";
import { CreateGroupDialog } from "./create-group-dialog";
import { useMyFeatures } from "./features";
import { GroupSwitcher } from "./group-switcher";
import { JoinByLinkSheet } from "./join-by-link-sheet";
import { ChevronIcon } from "./ui/icons";
import { useApiGet } from "./use-api";
import { useCurrentGroup } from "./use-current-group";

const ROW =
  "flex w-full min-h-16 cursor-pointer items-center gap-3 px-4 py-3 text-left text-ink no-underline " +
  "transition-colors duration-150 hover:bg-bg";

function today(): string {
  const now = new Date();
  return `${String(now.getFullYear())}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function RowBody({ item, fresh }: { item: MoreItem; fresh: boolean }) {
  return (
    <>
      <span className="flex min-w-0 grow flex-col gap-0.5">
        <span className="flex items-center gap-2 text-lead font-bold">
          {item.label}
          {fresh && <span className="rounded-full bg-ball px-2 py-0.5 text-meta font-bold text-on-ball">New</span>}
        </span>
        <span className="text-small text-muted">{item.description}</span>
      </span>
      <span className="shrink-0 text-muted">
        <ChevronIcon />
      </span>
    </>
  );
}

/** Everything Popshot does, grouped, with a search and a crew picker. Only what works for you. */
export function MoreView() {
  const router = useRouter();
  const { busy, signOut } = useAuth();
  const features = useMyFeatures();
  const searchId = useId();
  const [query, setQuery] = useState("");
  const groupsResult = useApiGet<GroupSummary[]>("/v1/groups");
  const groups =
    groupsResult.result.kind === "ready" ? groupsResult.result.data.filter((g) => g.my_status === "active") : [];
  const { current, choose } = useCurrentGroup(groups);
  const crewId = current?.id ?? null;
  const date = today();

  const items = searchItems(
    availableItems(MORE_ITEMS, { crewId, featureOn: (key) => featureOn(features, key, crewId) }),
    query,
  );
  const searching = query.trim().length > 0;

  function row(item: MoreItem): ReactNode {
    const body = <RowBody item={item} fresh={isNew(item, date)} />;
    if (item.href) {
      return (
        <Link href={item.href(crewId)} className={ROW}>
          {body}
        </Link>
      );
    }
    const button = (
      <button type="button" className={ROW} disabled={item.action === "sign-out" && busy}>
        {body}
      </button>
    );
    switch (item.action) {
      case "start-crew":
        return (
          <CreateGroupDialog
            trigger={button}
            onCreated={(group) => {
              router.push(`/groups/${group.id}`);
            }}
          />
        );
      case "join-crew":
        return <JoinByLinkSheet trigger={button} />;
      case "sign-out":
        return (
          <button type="button" className={ROW} disabled={busy} onClick={() => void signOut()}>
            {body}
          </button>
        );
      default:
        return null;
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <header className="flex animate-rise flex-col gap-1">
        <h1 className="text-display-sm leading-tight font-extrabold tracking-[-0.02em] font-display">More</h1>
        <p className="text-body text-muted">Everything Popshot does, in one place.</p>
      </header>

      <div className="flex flex-col gap-1.5">
        <label htmlFor={searchId} className="text-small font-bold">
          Search
        </label>
        <input
          id={searchId}
          type="search"
          value={query}
          autoComplete="off"
          placeholder="Try “invite” or “stats”"
          onChange={(event) => {
            setQuery(event.target.value);
          }}
          className="min-h-12 rounded-xl border border-line bg-surface px-4 text-field"
        />
        <p role="status" className="text-small text-muted empty:hidden">
          {searching ? (items.length === 1 ? "1 match" : `${String(items.length)} matches`) : ""}
        </p>
      </div>

      {current && groups.length > 1 && !searching && (
        <GroupSwitcher groups={groups} current={current} onChange={choose} />
      )}

      {searching && items.length === 0 && (
        <p className="rounded-2xl border border-dashed border-line p-4 text-body text-muted">
          Nothing matches “{query.trim()}”. Try another word, or tell us what you were looking for in{" "}
          <Link href="/contact">Help and feedback</Link>.
        </p>
      )}

      {SECTIONS.map((section) => {
        const inSection = items.filter((item) => item.section === section);
        if (inSection.length === 0) {
          return null;
        }
        const headingId = `more-${section}`;
        const crewName = section === "crew" && current && groups.length === 1 ? ` · ${current.name}` : "";
        return (
          <section key={section} aria-labelledby={headingId} className="flex animate-rise flex-col gap-2">
            <h2 id={headingId} className="text-label font-bold tracking-[0.1em] text-muted uppercase">
              {SECTION_LABEL[section]}
              {crewName}
            </h2>
            <ul className="divide-y divide-line overflow-hidden rounded-2xl border border-line bg-surface">
              {inSection.map((item) => (
                <li key={item.id}>{row(item)}</li>
              ))}
            </ul>
          </section>
        );
      })}
    </main>
  );
}
