"use client";

import { useEffect, useId, useRef, useState, type SubmitEvent } from "react";

import { apiDelete, apiGet, apiPost, apiPut, ApiError } from "@/lib/api-client";
import { COURT_MAX, hasLink } from "@/lib/crew-profile";
import type { GroupDetail } from "@/lib/groups";
import {
  mapsUrl,
  newSession,
  pickProblem,
  searchText,
  SEARCH_MAX,
  SEARCH_PAUSE_MS,
  type PickOutcome,
  type PlaceSuggestion,
  type SearchResult,
} from "@/lib/places";

import { useSignedIn } from "./auth";
import { buttonClass } from "./ui/button";

type Found =
  | { kind: "idle" }
  | { kind: "searching" }
  | { kind: "ready"; suggestions: PlaceSuggestion[] }
  | { kind: "problem"; message: string };

const field = "min-h-12 rounded-xl border border-line bg-bg px-4 text-field text-ink";

function problemOf(error: unknown, fallback: string): string {
  // 429 (a lot of searching this hour) and 503 (resting until tomorrow) carry their own words.
  if (error instanceof ApiError && (error.status === 429 || error.status === 503) && error.detail) {
    return error.detail;
  }
  return fallback;
}

/** The crew's court on the map: search Google Maps, pick a place, and name it in the crew's own words. */
export function CourtPicker({ group, onSaved }: { group: GroupDetail; onSaved: (group: GroupDetail) => void }) {
  const { user } = useSignedIn();
  const [editing, setEditing] = useState(!group.home_place);
  const [typed, setTyped] = useState("");
  const [found, setFound] = useState<Found>({ kind: "idle" });
  const [picked, setPicked] = useState<PlaceSuggestion | null>(null);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ text: string; warn: boolean } | null>(null);
  // One Google session from the first keystroke to the pick.
  const session = useRef<string>(newSession());
  // Only the latest search's answer counts.
  const latest = useRef(0);
  const nameRef = useRef<HTMLInputElement>(null);
  const resultsId = useId();

  const query = editing && !picked ? searchText(typed) : null;
  useEffect(() => {
    if (query === null) {
      return;
    }
    const ask = ++latest.current;
    const timer = window.setTimeout(() => {
      setFound({ kind: "searching" });
      apiPost<SearchResult>(user, `/v1/groups/${group.id}/places/search`, { text: query, session: session.current })
        .then((result) => {
          if (ask !== latest.current) return;
          setFound(
            result.unavailable
              ? { kind: "problem", message: "Court search isn't working just now. You can still list courts below." }
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
  }, [query, user, group.id]);

  function startOver() {
    session.current = newSession();
    latest.current++;
    setPicked(null);
    setName("");
    setTyped("");
    setFound({ kind: "idle" });
  }

  function choose(suggestion: PlaceSuggestion) {
    setPicked(suggestion);
    setMessage(null);
    // Focus the name next; the effect below can't, the field isn't there yet.
    window.setTimeout(() => nameRef.current?.focus(), 0);
  }

  async function save(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!picked) return;
    const label = name.trim();
    if (!label) {
      nameRef.current?.focus();
      return;
    }
    if (hasLink(label)) {
      setMessage({ text: "Leave out links and web or email addresses.", warn: true });
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      const answer = await apiPut<{ outcome: PickOutcome; group: GroupDetail }>(
        user,
        `/v1/groups/${group.id}/home-place`,
        { place_id: picked.place_id, session: session.current, label },
      );
      onSaved(answer.group);
      const problem = pickProblem(answer.outcome);
      if (problem) {
        setMessage({ text: problem, warn: true });
        startOver();
        return;
      }
      startOver();
      setEditing(false);
      setMessage({ text: "Saved.", warn: false });
    } catch (error) {
      setMessage({
        text:
          error instanceof ApiError && error.status === 422
            ? "Check the name: no links, and keep it short."
            : problemOf(error, "We couldn't save that just now."),
        warn: true,
      });
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    setSaving(true);
    setMessage(null);
    try {
      await apiDelete(user, `/v1/groups/${group.id}/home-place`);
      onSaved(await apiGet<GroupDetail>(user, `/v1/groups/${group.id}`));
      startOver();
      setEditing(true);
      setMessage({ text: "Removed.", warn: false });
    } catch {
      setMessage({ text: "We couldn't remove it just now.", warn: true });
    } finally {
      setSaving(false);
    }
  }

  const status = (
    <p role="status" className={`text-body ${message?.warn ? "text-warn" : "text-muted"} empty:hidden`}>
      {message?.text ?? ""}
    </p>
  );

  if (!editing && group.home_place) {
    const link = mapsUrl(group.home_place_google_id, group.home_place);
    return (
      <div className="flex flex-col gap-3">
        <p className="text-lead font-bold break-words">{group.home_place}</p>
        {link && (
          <a
            href={link}
            target="_blank"
            rel="noopener noreferrer"
            className="self-start text-body font-bold text-primary"
          >
            Open in Maps ↗
          </a>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            className={buttonClass("quiet")}
            onClick={() => {
              setEditing(true);
              setMessage(null);
            }}
          >
            Change
          </button>
          <button type="button" className={buttonClass("quiet")} disabled={saving} onClick={() => void remove()}>
            {saving ? "Removing…" : "Remove"}
          </button>
          {status}
        </div>
      </div>
    );
  }

  if (picked) {
    return (
      <form className="flex flex-col gap-4" onSubmit={(event) => void save(event)} noValidate>
        <p className="text-body">
          <span className="font-bold">{picked.main}</span>
          {picked.secondary && <span className="text-muted">, {picked.secondary}</span>}
        </p>
        <label className="flex flex-col gap-2">
          <span className="text-body font-bold">What does your crew call it?</span>
          <input
            ref={nameRef}
            value={name}
            onChange={(event) => {
              setName(event.target.value);
              setMessage(null);
            }}
            maxLength={COURT_MAX}
            autoComplete="off"
            placeholder="Riverside courts"
            className={field}
          />
          <span className="text-meta text-muted">In your own words. Members see this name.</span>
        </label>
        <div className="flex flex-wrap items-center gap-3">
          <button type="submit" className={buttonClass("primary")} disabled={saving || !name.trim()}>
            {saving ? "Saving…" : "Save court"}
          </button>
          <button type="button" className={buttonClass("quiet")} disabled={saving} onClick={startOver}>
            Pick another
          </button>
          {status}
        </div>
      </form>
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
            setMessage(null);
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
                      choose(suggestion);
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
      {(Boolean(group.home_place) || message !== null) && (
        <div className="flex flex-wrap items-center gap-3">
          {group.home_place && (
            <button
              type="button"
              className={buttonClass("quiet")}
              onClick={() => {
                startOver();
                setEditing(false);
              }}
            >
              Keep {group.home_place}
            </button>
          )}
          {status}
        </div>
      )}
    </div>
  );
}
