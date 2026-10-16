"use client";

import { useEffect, useId, useRef, useState, type ReactNode, type SubmitEvent } from "react";

import { apiDelete, apiGet, apiPatch, apiPost, ApiError } from "@/lib/api-client";
import { COURTS_MAX, courtMapsUrl, inOrder, type Court } from "@/lib/courts";
import { COURT_MAX, hasLink } from "@/lib/crew-profile";
import type { GroupDetail } from "@/lib/groups";
import {
  newSession,
  pickProblem,
  PLACES_FEATURE,
  searchText,
  SEARCH_MAX,
  SEARCH_PAUSE_MS,
  type PickOutcome,
  type PlaceSuggestion,
  type SearchResult,
} from "@/lib/places";

import { useSignedIn } from "./auth";
import { useFeature } from "./features";
import { buttonClass } from "./ui/button";

type Adding = { kind: "closed" } | { kind: "typed" } | { kind: "search" } | { kind: "name"; place: PlaceSuggestion };
type Found =
  | { kind: "idle" }
  | { kind: "searching" }
  | { kind: "ready"; suggestions: PlaceSuggestion[] }
  | { kind: "problem"; message: string };

const field = "min-h-12 rounded-xl border border-line bg-bg px-4 text-field text-ink";

function problemOf(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.detail && error.status !== 422) {
    return error.detail;
  }
  return error instanceof ApiError && error.status === 422 ? "Check the name: no links, and keep it short." : fallback;
}

/** A crew's saved courts (ADR 0007): up to five, one the default. Leads and co-leads add one by
 *  typing its name or, with court search on, by finding it on Google Maps and naming it. */
export function CrewCourts({ group, onSaved }: { group: GroupDetail; onSaved: (group: GroupDetail) => void }) {
  const { user } = useSignedIn();
  const searchOn = useFeature(PLACES_FEATURE, group.id);
  const courts = inOrder(group.courts ?? []);
  const [adding, setAdding] = useState<Adding>({ kind: "closed" });
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; warn: boolean } | null>(null);
  const base = `/v1/groups/${group.id}/courts` as const;

  async function run(work: () => Promise<GroupDetail>, done: string) {
    setBusy(true);
    setMessage(null);
    try {
      onSaved(await work());
      setMessage({ text: done, warn: false });
      setAdding({ kind: "closed" });
    } catch (error) {
      setMessage({ text: problemOf(error, "We couldn't save that just now."), warn: true });
    } finally {
      setBusy(false);
    }
  }

  async function add(label: string, place?: PlaceSuggestion, session?: string) {
    setBusy(true);
    setMessage(null);
    try {
      const answer = await apiPost<{ outcome: PickOutcome; group: GroupDetail }>(user, base, {
        label,
        ...(place ? { place_id: place.place_id, session } : {}),
      });
      onSaved(answer.group);
      const problem = pickProblem(answer.outcome);
      setMessage(problem ? { text: problem, warn: true } : { text: "Saved.", warn: false });
      setAdding(problem ? { kind: "search" } : { kind: "closed" });
    } catch (error) {
      setMessage({ text: problemOf(error, "We couldn't save that just now."), warn: true });
    } finally {
      setBusy(false);
    }
  }

  const status = (
    <p role="status" className={`text-body ${message?.warn ? "text-warn" : "text-muted"} empty:hidden`}>
      {message?.text ?? ""}
    </p>
  );

  return (
    <div className="flex flex-col gap-4">
      {courts.length === 0 ? (
        <p className="text-body text-muted">No courts saved yet.</p>
      ) : (
        <ul aria-label="Saved courts" className="flex flex-col gap-3">
          {courts.map((court) => (
            <CourtRow
              key={court.id}
              court={court}
              busy={busy}
              onDefault={() =>
                void run(() => apiPatch<GroupDetail>(user, `${base}/${court.id}`, { is_default: true }), "Saved.")
              }
              onRemove={() =>
                void run(async () => {
                  await apiDelete(user, `${base}/${court.id}`);
                  return apiGet<GroupDetail>(user, `/v1/groups/${group.id}`);
                }, "Removed.")
              }
            />
          ))}
        </ul>
      )}

      {courts.length >= COURTS_MAX ? (
        <p className="text-meta text-muted">A crew can save up to {String(COURTS_MAX)} courts.</p>
      ) : adding.kind === "closed" ? (
        <div className="flex flex-wrap gap-3">
          {searchOn && (
            <button
              type="button"
              className={buttonClass("quiet")}
              onClick={() => {
                setAdding({ kind: "search" });
              }}
            >
              Find on the map
            </button>
          )}
          <button
            type="button"
            className={buttonClass("quiet")}
            onClick={() => {
              setAdding({ kind: "typed" });
            }}
          >
            {searchOn ? "Type a name" : "Add a court"}
          </button>
        </div>
      ) : adding.kind === "typed" ? (
        <NameForm
          label="Court name"
          hint="A court or park name, not a home address."
          busy={busy}
          onCancel={() => {
            setAdding({ kind: "closed" });
          }}
          onSave={(label) => void add(label)}
          onProblem={(text) => {
            setMessage({ text, warn: true });
          }}
        />
      ) : (
        <PlaceSearch
          groupId={group.id}
          busy={busy}
          onCancel={() => {
            setAdding({ kind: "closed" });
          }}
          onSave={(label, place, session) => void add(label, place, session)}
          onProblem={(text) => {
            setMessage({ text, warn: true });
          }}
        />
      )}
      {status}
    </div>
  );
}

function CourtRow({
  court,
  busy,
  onDefault,
  onRemove,
}: {
  court: Court;
  busy: boolean;
  onDefault: () => void;
  onRemove: () => void;
}) {
  const link = courtMapsUrl(court);
  return (
    <li className="flex flex-col gap-2 rounded-2xl border border-line p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-body font-bold break-words">{court.label}</span>
        {court.is_default && (
          <span className="rounded-full bg-primary px-2.5 py-0.5 text-meta font-bold text-on-primary">Default</span>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        {link && (
          <a href={link} target="_blank" rel="noopener noreferrer" className="text-body font-bold text-primary">
            Open in Maps ↗
          </a>
        )}
        {!court.is_default && (
          <button
            type="button"
            className="min-h-11 text-body font-bold text-primary"
            disabled={busy}
            aria-label={`Make ${court.label} the default`}
            onClick={onDefault}
          >
            Make default
          </button>
        )}
        <button
          type="button"
          className="min-h-11 text-body font-bold text-warn"
          disabled={busy}
          aria-label={`Remove ${court.label}`}
          onClick={onRemove}
        >
          Remove
        </button>
      </div>
    </li>
  );
}

function NameForm({
  label,
  hint,
  above,
  busy,
  onCancel,
  onSave,
  onProblem,
}: {
  label: string;
  hint: string;
  above?: ReactNode;
  busy: boolean;
  onCancel: () => void;
  onSave: (label: string) => void;
  onProblem: (text: string) => void;
}) {
  const [name, setName] = useState("");
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    ref.current?.focus();
  }, []);

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const clean = name.trim();
    if (!clean) {
      ref.current?.focus();
      return;
    }
    if (hasLink(clean)) {
      onProblem("Leave out links and web or email addresses.");
      return;
    }
    onSave(clean);
  }

  return (
    <form className="flex flex-col gap-3" onSubmit={submit} noValidate>
      {above}
      <label className="flex flex-col gap-2">
        <span className="text-body font-bold">{label}</span>
        <input
          ref={ref}
          value={name}
          onChange={(event) => {
            setName(event.target.value);
          }}
          maxLength={COURT_MAX}
          autoComplete="off"
          placeholder="Riverside courts"
          className={field}
        />
        <span className="text-meta text-muted">{hint}</span>
      </label>
      <div className="flex flex-wrap gap-3">
        <button type="submit" className={buttonClass("primary")} disabled={busy || !name.trim()}>
          {busy ? "Saving…" : "Save court"}
        </button>
        <button type="button" className={buttonClass("quiet")} disabled={busy} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
}

function PlaceSearch({
  groupId,
  busy,
  onCancel,
  onSave,
  onProblem,
}: {
  groupId: string;
  busy: boolean;
  onCancel: () => void;
  onSave: (label: string, place: PlaceSuggestion, session: string) => void;
  onProblem: (text: string) => void;
}) {
  const { user } = useSignedIn();
  const [typed, setTyped] = useState("");
  const [found, setFound] = useState<Found>({ kind: "idle" });
  const [picked, setPicked] = useState<PlaceSuggestion | null>(null);
  // One Google session from the first keystroke to the pick.
  const session = useRef<string>(newSession());
  // Only the latest search's answer counts.
  const latest = useRef(0);
  const resultsId = useId();

  const query = picked ? null : searchText(typed);
  useEffect(() => {
    if (query === null) {
      return;
    }
    const ask = ++latest.current;
    const timer = window.setTimeout(() => {
      setFound({ kind: "searching" });
      apiPost<SearchResult>(user, `/v1/groups/${groupId}/places/search`, { text: query, session: session.current })
        .then((result) => {
          if (ask !== latest.current) return;
          setFound(
            result.unavailable
              ? { kind: "problem", message: "Court search isn't working just now. You can type a name instead." }
              : { kind: "ready", suggestions: result.suggestions },
          );
        })
        .catch((error: unknown) => {
          if (ask !== latest.current) return;
          setFound({ kind: "problem", message: problemOf(error, "We couldn't search just now.") });
        });
    }, SEARCH_PAUSE_MS);
    return () => {
      window.clearTimeout(timer);
    };
  }, [query, user, groupId]);

  if (picked) {
    return (
      <NameForm
        label="What does your crew call it?"
        hint="In your own words. Members see this name."
        above={
          <p className="text-body">
            <span className="font-bold">{picked.main}</span>
            {picked.secondary && <span className="text-muted">, {picked.secondary}</span>}
          </p>
        }
        busy={busy}
        onCancel={onCancel}
        onSave={(label) => {
          onSave(label, picked, session.current);
        }}
        onProblem={onProblem}
      />
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <label className="flex flex-col gap-2">
        <span className="text-body font-bold">Search for your court</span>
        <input
          type="search"
          value={typed}
          onChange={(event) => {
            setTyped(event.target.value);
            if (!searchText(event.target.value)) {
              latest.current++;
              setFound({ kind: "idle" });
            }
          }}
          maxLength={SEARCH_MAX}
          autoComplete="off"
          enterKeyHint="search"
          placeholder="Park, club or court name"
          aria-controls={resultsId}
          className={field}
        />
        <span className="text-meta text-muted">A park, club or court, never someone&apos;s home.</span>
      </label>
      <div id={resultsId} aria-live="polite" className="flex flex-col gap-2">
        {found.kind === "searching" && <p className="text-body text-muted">Searching…</p>}
        {found.kind === "problem" && <p className="text-body text-warn">{found.message}</p>}
        {found.kind === "ready" && found.suggestions.length === 0 && (
          <p className="text-body text-muted">Nothing found. Try another name.</p>
        )}
        {found.kind === "ready" && found.suggestions.length > 0 && (
          <>
            <ul aria-label="Courts found" className="flex flex-col gap-2">
              {found.suggestions.map((suggestion) => (
                <li key={suggestion.place_id}>
                  <button
                    type="button"
                    onClick={() => {
                      setPicked(suggestion);
                    }}
                    className="flex min-h-12 w-full flex-col items-start justify-center rounded-xl border border-line px-4 py-2 text-left hover:border-primary focus-visible:outline-3 focus-visible:outline-offset-2 focus-visible:outline-primary"
                  >
                    <span className="text-body font-bold break-words">{suggestion.main}</span>
                    {suggestion.secondary && (
                      <span className="text-meta text-muted break-words">{suggestion.secondary}</span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
            <p className="text-meta text-muted">Results from Google Maps</p>
          </>
        )}
      </div>
      <button type="button" className={buttonClass("quiet", "self-start")} onClick={onCancel}>
        Cancel
      </button>
    </div>
  );
}
