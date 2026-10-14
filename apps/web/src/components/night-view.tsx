"use client";

import Link from "next/link";
import { useState } from "react";

import { apiPost, ApiError } from "@/lib/api-client";
import { myStatus, nightWhen, spotsLine, type Night, type NightPerson } from "@/lib/nights";

import { useSignedIn } from "./auth";
import { PlanNightSheet } from "./plan-night-sheet";
import { RsvpButtons } from "./rsvp-buttons";
import { useApiGet } from "./use-api";
import { Avatar } from "./ui/avatar";
import { buttonClass } from "./ui/button";
import { BackIcon } from "./ui/icons";
import { Sheet } from "./ui/sheet";

export function NightView({ groupId, nightId }: { groupId: string; nightId: string }) {
  const { result, reload, replace } = useApiGet<Night>(`/v1/groups/${groupId}/nights/${nightId}`);

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-5 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <Link
        href={`/groups/${groupId}`}
        className="-ml-1 flex min-h-11 items-center gap-1.5 self-start text-body font-bold text-primary no-underline"
      >
        <BackIcon />
        {result.kind === "ready" ? result.data.group_name : "Back to the group"}
      </Link>
      {result.kind === "loading" && <p className="text-muted">Loading the meetup…</p>}
      {result.kind === "error" && result.status === 404 && (
        <section className="flex flex-col gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-5">
          <h1 className="text-title-lg font-extrabold">We couldn&apos;t find that meetup.</h1>
        </section>
      )}
      {result.kind === "error" && result.status !== 404 && (
        <div
          role="alert"
          className="flex flex-col items-start gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-5"
        >
          <p>We couldn&apos;t load this meetup just now.</p>
          <button type="button" className={buttonClass("quiet")} onClick={reload}>
            Try again
          </button>
        </div>
      )}
      {result.kind === "ready" && <NightDetail night={result.data} onChange={replace} />}
    </main>
  );
}

function NightDetail({ night, onChange }: { night: Night; onChange: (night: Night) => void }) {
  const status = myStatus(night);
  return (
    <>
      <section className="flex animate-rise flex-col gap-1">
        {night.cancelled && (
          <p className="self-start rounded-full bg-chip px-3 py-1 text-small font-bold text-warn">Cancelled</p>
        )}
        <h1 className="text-display-sm leading-tight font-extrabold font-display">{nightWhen(night.starts_at)}</h1>
        <p className="text-title-sm font-bold">{night.venue}</p>
        {night.note && <p className="text-lead text-muted">{night.note}</p>}
        <p className="text-small text-muted">
          Planned by {night.created_by_name} · {spotsLine(night)}
        </p>
      </section>

      {night.open && (
        <section
          aria-label="Your answer"
          className="flex animate-rise flex-col gap-2 rounded-3xl border border-transparent bg-surface shadow-card p-4"
        >
          {status && <p className="font-bold">{status}</p>}
          <RsvpButtons night={night} onChange={onChange} />
        </section>
      )}
      {!night.open && !night.cancelled && <p className="text-muted">Answers for this meetup have closed.</p>}

      <PeopleList
        title={`Going · ${String(night.going.length)}${night.spots ? ` of ${String(night.spots)}` : ""}`}
        people={night.going}
      />
      <PeopleList title={`Waitlist · ${String(night.waitlist.length)}`} people={night.waitlist} numbered />
      <PeopleList title={`Maybe · ${String(night.maybe.length)}`} people={night.maybe} />
      <PeopleList title={`Can't make it · ${String(night.out.length)}`} people={night.out} />

      {night.can_edit && !night.cancelled && (
        <div className="flex flex-wrap gap-2 border-t border-line pt-5">
          <PlanNightSheet
            groupId={night.group_id}
            editing={night}
            onSaved={onChange}
            trigger={
              <button type="button" className={buttonClass("quiet", "min-h-11 px-4 text-body")}>
                Change details
              </button>
            }
          />
          <CancelNight night={night} onCancelled={onChange} />
        </div>
      )}
    </>
  );
}

function PeopleList({ title, people, numbered = false }: { title: string; people: NightPerson[]; numbered?: boolean }) {
  if (people.length === 0) {
    return null;
  }
  const id = `list-${title.split(" ")[0]?.toLowerCase() ?? "people"}`;
  return (
    <section aria-labelledby={id} className="flex animate-rise flex-col gap-2">
      <h2 id={id} className="text-title-sm font-bold text-ink">
        {title}
      </h2>
      <ul className="overflow-hidden rounded-3xl border border-transparent bg-surface shadow-card">
        {people.map((person, index) => (
          <li
            key={person.user_id}
            className="flex min-h-14 items-center gap-3 border-b border-line px-4 py-2 last:border-b-0"
          >
            {numbered && <span className="w-5 text-center font-extrabold text-muted tabular-nums">{index + 1}</span>}
            <Avatar name={person.display_name} photoUrl={person.avatar_url} size="sm" />
            <span className="truncate text-lead font-bold">{person.display_name}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function CancelNight({ night, onCancelled }: { night: Night; onCancelled: (night: Night) => void }) {
  const { user } = useSignedIn();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function cancel() {
    setBusy(true);
    setProblem(null);
    try {
      onCancelled(await apiPost<Night>(user, `/v1/groups/${night.group_id}/nights/${night.id}/cancel`, {}));
      setOpen(false);
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "We couldn't cancel it just now.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet
      trigger={
        <button type="button" className={buttonClass("danger", "min-h-11 px-4 text-body")}>
          Cancel night
        </button>
      }
      open={open}
      onOpenChange={setOpen}
      title="Cancel this meetup?"
      description="Everyone who said they're in or maybe gets a notification. This can't be undone."
    >
      <div className="flex flex-col gap-3">
        <p role="alert" className="text-body text-warn empty:hidden">
          {problem}
        </p>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            className={buttonClass("quiet")}
            onClick={() => {
              setOpen(false);
            }}
          >
            Keep it
          </button>
          <button type="button" className={buttonClass("danger")} disabled={busy} onClick={() => void cancel()}>
            Cancel night
          </button>
        </div>
      </div>
    </Sheet>
  );
}
