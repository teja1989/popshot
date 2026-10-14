"use client";

import { useEffect, useState, type SubmitEvent } from "react";

import { apiDelete, apiGet, apiPost, ApiError } from "@/lib/api-client";
import { normalizeCode, STANDING_LABEL, type GroupDirectInvite, type Person } from "@/lib/direct-invites";
import { describeExpiry } from "@/lib/invites";

import { useSignedIn } from "./auth";
import { useApiGet } from "./use-api";
import { Avatar } from "./ui/avatar";
import { buttonClass } from "./ui/button";
import { PlusIcon } from "./ui/icons";
import { Sheet } from "./ui/sheet";

const SEARCH_DELAY_MS = 250;

/** For leads and co-leads: invite people you know, or someone by their Popshot code. */
export function InvitePeople({ groupId }: { groupId: string }) {
  const { user } = useSignedIn();
  const { result, reload } = useApiGet<GroupDirectInvite[]>(`/v1/groups/${groupId}/direct-invites`);
  const [problem, setProblem] = useState<string | null>(null);

  async function cancel(invite: GroupDirectInvite) {
    setProblem(null);
    try {
      await apiDelete(user, `/v1/groups/${groupId}/direct-invites/${invite.id}`);
    } catch (error) {
      // Already answered or gone is fine: the list refreshes below.
      if (!(error instanceof ApiError && error.status === 404)) {
        setProblem("We couldn't cancel that invite just now. Try again in a moment.");
      }
    }
    reload();
  }

  return (
    <section aria-labelledby="people-heading" className="flex animate-rise flex-col gap-3 [animation-delay:150ms]">
      <h2 id="people-heading" className="text-title-sm font-bold text-ink">
        Invite people
      </h2>
      <div className="flex flex-col gap-4 rounded-3xl border border-transparent bg-surface shadow-card p-5">
        <p className="text-muted">
          Invite someone you&apos;ve played with, or anyone who gives you their Popshot code. They&apos;ll see it on
          their Home screen. Saying yes puts them straight in.
        </p>
        <InviteSheet groupId={groupId} onSent={reload} />

        {result.kind === "ready" && result.data.length > 0 && (
          <ul
            className="-mb-2 flex flex-col divide-y divide-line border-t border-line"
            aria-label="Waiting for an answer"
          >
            {result.data.map((invite) => (
              <li key={invite.id} className="flex items-center gap-3 py-3">
                <Avatar name={invite.display_name} photoUrl={invite.avatar_url} size="sm" />
                <div className="min-w-0 grow">
                  <p className="truncate font-bold">{invite.display_name}</p>
                  <p className="text-small text-muted">Invited · {describeExpiry(invite.expires_at)}</p>
                </div>
                <button
                  type="button"
                  className={buttonClass("quiet", "min-h-11 shrink-0 px-4 text-body")}
                  onClick={() => void cancel(invite)}
                >
                  Cancel
                </button>
              </li>
            ))}
          </ul>
        )}
        {problem && (
          <p role="alert" className="text-warn">
            {problem}
          </p>
        )}
      </div>
    </section>
  );
}

function InviteSheet({ groupId, onSent }: { groupId: string; onSent: () => void }) {
  const { user } = useSignedIn();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [known, setKnown] = useState<Person[] | null>(null);
  const [code, setCode] = useState("");
  const [found, setFound] = useState<Person | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  // People you know, as you type.
  useEffect(() => {
    if (!open) {
      return;
    }
    let current = true;
    const timer = setTimeout(() => {
      apiGet<Person[]>(user, `/v1/groups/${groupId}/people?q=${encodeURIComponent(query.trim())}`)
        .then((people) => {
          if (current) {
            setKnown(people);
          }
        })
        .catch(() => {
          if (current) {
            setKnown([]);
          }
        });
    }, SEARCH_DELAY_MS);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [open, query, user, groupId]);

  function reset() {
    setQuery("");
    setKnown(null);
    setCode("");
    setFound(null);
    setNote(null);
  }

  function problemOf(error: unknown): string {
    return error instanceof ApiError && error.detail ? error.detail : "That didn't work just now. Try again.";
  }

  async function invite(person: Person) {
    setBusy(true);
    setNote(null);
    try {
      await apiPost(user, `/v1/groups/${groupId}/direct-invites`, { user_id: person.user_id });
      const invited = { ...person, standing: "invited" as const };
      setKnown((people) => people?.map((p) => (p.user_id === person.user_id ? invited : p)) ?? null);
      setFound((current) => (current?.user_id === person.user_id ? invited : current));
      setNote(`Invite sent to ${person.display_name}.`);
      onSent();
    } catch (error) {
      setNote(problemOf(error));
    } finally {
      setBusy(false);
    }
  }

  async function lookUp(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setFound(null);
    setNote(null);
    if (normalizeCode(code) === null) {
      setNote("A Popshot code has 8 letters and numbers, like K7M2-QX4P.");
      return;
    }
    setBusy(true);
    try {
      const { person } = await apiPost<{ person: Person | null }>(user, `/v1/groups/${groupId}/people/lookup`, {
        code,
      });
      setFound(person);
      if (!person) {
        setNote("No one has that code. Check it with them; they can find it on their You page.");
      }
    } catch (error) {
      setNote(problemOf(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet
      trigger={
        <button type="button" className={buttonClass("primary", "self-start")}>
          <PlusIcon />
          Invite someone
        </button>
      }
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          reset();
        }
        setOpen(next);
      }}
      title="Invite someone"
      description="They'll see it on their Home screen and can say yes or no."
      fullOnPhone
    >
      <div className="flex flex-col gap-6">
        <section aria-labelledby="known-heading" className="flex flex-col gap-2">
          <h3 id="known-heading" className="text-lead font-extrabold">
            People you&apos;ve played with
          </h3>
          <label className="flex flex-col gap-1">
            <span className="text-body font-bold">Search by name</span>
            <input
              type="search"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
              }}
              maxLength={80}
              autoComplete="off"
              className="min-h-12 rounded-xl border border-line bg-bg px-4 text-field text-ink"
            />
          </label>
          {known !== null && known.length === 0 && (
            <p className="text-body text-muted">
              {query.trim() ? "No one by that name from your crews." : "No one from your crews yet."}
            </p>
          )}
          {known !== null && known.length > 0 && (
            <ul className="flex flex-col divide-y divide-line" aria-label="People you know">
              {known.map((person) => (
                <PersonRow key={person.user_id} person={person} busy={busy} onInvite={() => void invite(person)} />
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="code-heading" className="flex flex-col gap-2 border-t border-line pt-5">
          <h3 id="code-heading" className="text-lead font-extrabold">
            Or use their Popshot code
          </h3>
          <form className="flex flex-col gap-2" onSubmit={(event) => void lookUp(event)}>
            <label className="flex flex-col gap-1">
              <span className="text-body font-bold">Their code</span>
              <input
                value={code}
                onChange={(event) => {
                  setCode(event.target.value);
                  setFound(null);
                }}
                maxLength={32}
                autoComplete="off"
                autoCapitalize="characters"
                spellCheck={false}
                placeholder="K7M2-QX4P"
                className="min-h-12 rounded-xl border border-line bg-bg px-4 font-mono text-field tracking-wider text-ink uppercase"
              />
            </label>
            <button type="submit" className={buttonClass("quiet", "self-start")} disabled={busy}>
              Find
            </button>
          </form>
          {found && (
            <ul aria-label="Found by code">
              <PersonRow person={found} busy={busy} onInvite={() => void invite(found)} />
            </ul>
          )}
        </section>

        <p role="status" className="min-h-6 text-body text-muted">
          {note}
        </p>
      </div>
    </Sheet>
  );
}

function PersonRow({ person, busy, onInvite }: { person: Person; busy: boolean; onInvite: () => void }) {
  return (
    <li className="flex min-h-16 items-center gap-3 py-2">
      <Avatar name={person.display_name} photoUrl={person.avatar_url} size="sm" />
      <span className="min-w-0 grow truncate font-bold">{person.display_name}</span>
      {person.standing ? (
        <span className="shrink-0 rounded-full bg-chip px-3 py-1 text-small font-bold text-muted">
          {STANDING_LABEL[person.standing]}
        </span>
      ) : (
        <button
          type="button"
          className={buttonClass("action", "min-h-11 shrink-0 px-4 text-body")}
          disabled={busy}
          onClick={onInvite}
          aria-label={`Invite ${person.display_name}`}
        >
          Invite
        </button>
      )}
    </li>
  );
}
