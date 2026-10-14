"use client";

import Link from "next/link";
import { useState } from "react";

import { apiPost, apiPut } from "@/lib/api-client";
import { labelFor, type FocusOption } from "@/lib/focus";
import {
  bodyOf,
  draftOf,
  draftReady,
  LEVEL_LABEL,
  LEVELS,
  MAX_SKILLS,
  type ItemDraft,
  type LibraryHost,
  type LibraryItem,
} from "@/lib/library";

import { ChangeSheet } from "./admin-change-sheet";
import { AdminGate, AdminMain, Section } from "./admin-ui";
import { useSignedIn } from "./auth";
import { FocusPicker } from "./focus-picker";
import { buttonClass } from "./ui/button";
import { segmentOption, segmentTrack } from "./ui/segmented";
import { useApiGet } from "./use-api";

const SMALL_BUTTON = "min-h-10 shrink-0 px-3 text-body whitespace-nowrap";
const INPUT = "min-h-12 rounded-xl border border-line bg-bg px-4 text-field text-ink";

type Show = "all" | "published" | "draft";

/**
 * The content library: videos and articles for the Journey tab. Players see published items
 * only. Every change needs a reason and is kept in the admin log. Admin only.
 */
export function AdminLibraryView() {
  const items = useApiGet<LibraryItem[]>("/v1/admin/content");
  const options = useApiGet<FocusOption[]>("/v1/focus-options");
  const status = items.result.kind === "error" ? items.result.status : null;
  const [show, setShow] = useState<Show>("all");
  const skillOptions = options.result.kind === "ready" ? options.result.data : [];

  return (
    <AdminGate status={status} onSignedIn={items.reload}>
      <AdminMain>
        <header className="flex animate-rise flex-col gap-1">
          <Link href="/admin" className="self-start text-small font-bold text-primary">
            ← Admin
          </Link>
          <h1 className="text-title-lg leading-tight font-extrabold">Library</h1>
          <p className="text-body text-muted">
            Videos and articles for players&apos; journeys, by skill and level. Only published ones are shown to
            players. Links open outside Popshot, and only from the sites listed below.
          </p>
        </header>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <fieldset className={`${segmentTrack} grid-cols-3`}>
            <legend className="sr-only">Show</legend>
            {(["all", "published", "draft"] as const).map((value) => (
              <label key={value} className={segmentOption}>
                <input
                  type="radio"
                  name="show"
                  className="sr-only"
                  checked={show === value}
                  onChange={() => {
                    setShow(value);
                  }}
                />
                {value === "all" ? "All" : value === "published" ? "Published" : "Drafts"}
              </label>
            ))}
          </fieldset>
          <ItemSheet item={null} options={skillOptions} onDone={items.reload} />
        </div>
        {items.result.kind === "loading" && <p className="text-muted">Loading the library…</p>}
        {items.result.kind === "error" && status !== 404 && status !== 403 && (
          <p role="alert" className="text-warn">
            We couldn&apos;t load the library just now.
          </p>
        )}
        {items.result.kind === "ready" && (
          <ItemList
            items={items.result.data.filter((i) => show === "all" || i.status === show)}
            options={skillOptions}
            onChanged={items.reload}
          />
        )}
        <Hosts />
      </AdminMain>
    </AdminGate>
  );
}

function ItemList({
  items,
  options,
  onChanged,
}: {
  items: LibraryItem[];
  options: FocusOption[];
  onChanged: () => void;
}) {
  if (items.length === 0) {
    return <p className="rounded-2xl border border-dashed border-line p-4 text-body text-muted">Nothing here yet.</p>;
  }
  return (
    <ul className="flex flex-col gap-3" aria-label="Library items">
      {items.map((item) => (
        <li
          key={item.id}
          className="flex flex-col gap-2 rounded-3xl border border-transparent bg-surface p-4 shadow-card"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="flex min-w-0 flex-col">
              <p className="text-lead font-extrabold break-words">{item.title}</p>
              <p className="text-small text-muted">
                {item.kind === "video" ? "Video" : "Article"} · {item.source}
                {item.minutes ? ` · ${String(item.minutes)} min` : ""}
              </p>
            </div>
            <span
              className={`rounded-full px-3 py-1 text-small font-bold ${
                item.status === "published" ? "bg-secondary-container text-on-secondary-container" : "bg-chip"
              }`}
            >
              {item.status === "published" ? "Published" : "Draft"}
            </span>
          </div>
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-small font-bold break-all text-primary"
          >
            {item.url}
          </a>
          <p className="text-small">
            {item.skills.map((s) => labelFor(options, s)).join(", ")}
            {" · "}
            {item.levels.length === 0 ? "Every level" : item.levels.map((l) => LEVEL_LABEL[l]).join(", ")}
          </p>
          <div className="flex flex-wrap gap-2">
            <ItemSheet item={item} options={options} onDone={onChanged} />
            <StatusSheet item={item} onDone={onChanged} />
          </div>
        </li>
      ))}
    </ul>
  );
}

function ItemSheet({
  item,
  options,
  onDone,
}: {
  item: LibraryItem | null;
  options: FocusOption[];
  onDone: () => void;
}) {
  const { user } = useSignedIn();
  const [draft, setDraft] = useState<ItemDraft>(() => draftOf(item));
  const set = (change: Partial<ItemDraft>) => {
    setDraft({ ...draft, ...change });
  };
  return (
    <ChangeSheet
      trigger={
        <button
          type="button"
          className={buttonClass(item ? "quiet" : "primary", SMALL_BUTTON)}
          aria-label={item ? `Edit ${item.title}` : undefined}
          onClick={() => {
            setDraft(draftOf(item));
          }}
        >
          {item ? "Edit" : "Add an item"}
        </button>
      }
      title={item ? "Edit this item" : "Add to the library"}
      description="New items start as drafts. Publish one when it's ready for players."
      confirm={item ? "Save changes" : "Add as a draft"}
      ready={draftReady(draft)}
      fields={
        <>
          <fieldset className={`${segmentTrack} grid-cols-2 self-start`}>
            <legend className="mb-1.5 font-bold">Kind</legend>
            {(["video", "article"] as const).map((kind) => (
              <label key={kind} className={segmentOption}>
                <input
                  type="radio"
                  name="kind"
                  className="sr-only"
                  checked={draft.kind === kind}
                  onChange={() => {
                    set({ kind });
                  }}
                />
                {kind === "video" ? "Video" : "Article"}
              </label>
            ))}
          </fieldset>
          <label className="flex flex-col gap-1.5">
            <span className="font-bold">Link</span>
            <input
              type="url"
              inputMode="url"
              value={draft.url}
              placeholder="https://www.youtube.com/watch?v=…"
              onChange={(event) => {
                set({ url: event.target.value });
              }}
              maxLength={500}
              className={INPUT}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="font-bold">Title</span>
            <input
              value={draft.title}
              onChange={(event) => {
                set({ title: event.target.value });
              }}
              maxLength={120}
              className={INPUT}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="font-bold">Channel or site</span>
            <input
              value={draft.source}
              onChange={(event) => {
                set({ source: event.target.value });
              }}
              maxLength={60}
              className={INPUT}
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="font-bold">Minutes (optional)</span>
            <input
              inputMode="numeric"
              value={draft.minutes}
              onChange={(event) => {
                set({ minutes: event.target.value });
              }}
              maxLength={3}
              className={`${INPUT} w-28`}
            />
          </label>
          <FocusPicker
            legend="Skills it helps with"
            hint={`1 to ${String(MAX_SKILLS)}.`}
            options={options}
            selected={draft.skills}
            onChange={(skills) => {
              set({ skills });
            }}
            max={MAX_SKILLS}
            compact
          />
          <fieldset className="flex flex-col gap-1.5">
            <legend className="mb-1.5 font-bold">Levels (none picked: every level)</legend>
            <div className="flex flex-wrap gap-1.5">
              {LEVELS.map((level) => (
                <button
                  key={level}
                  type="button"
                  aria-pressed={draft.levels.includes(level)}
                  onClick={() => {
                    set({
                      levels: draft.levels.includes(level)
                        ? draft.levels.filter((l) => l !== level)
                        : [...draft.levels, level],
                    });
                  }}
                  className="min-h-10 cursor-pointer rounded-full border-2 border-line px-3 text-small font-bold aria-pressed:border-primary aria-pressed:bg-primary aria-pressed:text-on-primary"
                >
                  {LEVEL_LABEL[level]}
                </button>
              ))}
            </div>
          </fieldset>
        </>
      }
      save={async (reason) => {
        if (item) {
          await apiPut(user, `/v1/admin/content/${item.id}`, bodyOf(draft, reason));
        } else {
          await apiPost(user, "/v1/admin/content", bodyOf(draft, reason));
        }
      }}
      onDone={onDone}
    />
  );
}

function StatusSheet({ item, onDone }: { item: LibraryItem; onDone: () => void }) {
  const { user } = useSignedIn();
  const publishing = item.status === "draft";
  return (
    <ChangeSheet
      trigger={
        <button
          type="button"
          className={buttonClass(publishing ? "primary" : "quiet", SMALL_BUTTON)}
          aria-label={`${publishing ? "Publish" : "Unpublish"} ${item.title}`}
        >
          {publishing ? "Publish" : "Unpublish"}
        </button>
      }
      title={publishing ? "Publish this item" : "Unpublish this item"}
      description={
        publishing
          ? `“${item.title}” will show on players' Journey tabs straight away.`
          : `“${item.title}” will stop showing to players straight away. It stays in the library as a draft.`
      }
      confirm={publishing ? "Publish" : "Unpublish"}
      save={async (reason) => {
        await apiPut(user, `/v1/admin/content/${item.id}/status`, {
          status: publishing ? "published" : "draft",
          reason,
        });
      }}
      onDone={onDone}
    />
  );
}

function Hosts() {
  const { user } = useSignedIn();
  const hosts = useApiGet<LibraryHost[]>("/v1/admin/content/hosts");
  const [host, setHost] = useState("");
  return (
    <Section title="Allowed sites">
      {hosts.result.kind === "ready" && (
        <ul className="flex flex-wrap gap-1.5" aria-label="Allowed sites">
          {hosts.result.data.map((h) => (
            <li key={h.host} className="rounded-full bg-chip px-3 py-1 text-small font-bold">
              {h.host}
            </li>
          ))}
        </ul>
      )}
      <ChangeSheet
        trigger={
          <button type="button" className={buttonClass("quiet", `${SMALL_BUTTON} self-start`)}>
            Allow a site
          </button>
        }
        title="Allow a site"
        description="Links from this site can then be added to the library. Only add sites you trust."
        confirm="Allow"
        ready={host.trim() !== ""}
        fields={
          <label className="flex flex-col gap-1.5">
            <span className="font-bold">Site</span>
            <input
              value={host}
              placeholder="www.example.com"
              onChange={(event) => {
                setHost(event.target.value);
              }}
              maxLength={100}
              className={INPUT}
            />
          </label>
        }
        save={async (reason) => {
          await apiPost(user, "/v1/admin/content/hosts", { host: host.trim(), reason });
          setHost("");
        }}
        onDone={hosts.reload}
      />
    </Section>
  );
}
