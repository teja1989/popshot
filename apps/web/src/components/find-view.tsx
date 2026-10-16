"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useRef, useState, type SubmitEvent } from "react";

import { apiPost, ApiError } from "@/lib/api-client";
import { hasLink, usualLine, type Day, type TimeOfDay } from "@/lib/crew-profile";
import {
  distanceLabel,
  loadStart,
  locationProblem,
  placeProblem,
  RADIUS_KM,
  REPORT_REASONS,
  saveStart,
  spaceLabel,
  type OpenCrew,
  type PlaceAnswer,
  type ReportReason,
  type Start,
} from "@/lib/open-crews";
import {
  mapsUrl,
  newSession,
  searchText,
  SEARCH_MAX,
  SEARCH_PAUSE_MS,
  type PlaceSuggestion,
  type SearchResult,
} from "@/lib/places";

import { useSignedIn } from "./auth";
import { buttonClass } from "./ui/button";
import { Sheet } from "./ui/sheet";

type Results =
  | { kind: "idle" }
  | { kind: "searching"; near: string }
  | { kind: "ready"; near: string; crews: OpenCrew[] }
  | { kind: "problem"; message: string };

const field = "min-h-12 rounded-xl border border-line bg-bg px-4 text-field text-ink placeholder:text-muted";

function problemOf(error: unknown, fallback: string): string {
  return error instanceof ApiError && error.detail ? error.detail : fallback;
}

function nearOf(start: Start): string {
  return start.kind === "here" ? "you" : start.label;
}

function errorCode(error: unknown): number | null {
  return typeof error === "object" && error !== null && "code" in error ? Number(error.code) : null;
}

function storage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/** Where the phone is, rounded to about a kilometre: close enough to sort crews by distance. */
function here(): Promise<{ lat: number; lng: number }> {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject(new Error("no location"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        resolve({
          lat: Math.round(position.coords.latitude * 100) / 100,
          lng: Math.round(position.coords.longitude * 100) / 100,
        });
      },
      reject,
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 600_000 },
    );
  });
}

/**
 * Find: open crews near you. Search from the phone's location, or from a town or park typed
 * in (through Google). How you searched is remembered on this device only, never where.
 */
export function FindView() {
  const { user } = useSignedIn();
  // Where you searched from last time on this device: searched again as the page opens.
  const [initial] = useState<Start | null>(() => loadStart(storage()));
  const [start, setStart] = useState<Start | null>(initial);
  const [choosing, setChoosing] = useState(initial === null);
  const [results, setResults] = useState<Results>(
    initial ? { kind: "searching", near: nearOf(initial) } : { kind: "idle" },
  );

  // Every state change here happens after an await: the search runs from an effect too.
  const look = useCallback(
    async (next: Start, session?: string) => {
      const near = nearOf(next);
      const fail = (message: string) => {
        saveStart(storage(), null);
        setStart(null);
        setChoosing(true);
        setResults({ kind: "problem", message });
      };
      try {
        let crews: OpenCrew[];
        if (next.kind === "here") {
          let point: { lat: number; lng: number };
          try {
            point = await here();
          } catch (error) {
            fail(locationProblem(errorCode(error)));
            return;
          }
          crews = await apiPost<OpenCrew[]>(user, "/v1/open-crews/search", { ...point, radius_km: RADIUS_KM });
        } else {
          const answer = await apiPost<PlaceAnswer>(user, "/v1/open-crews/search/place", {
            place_id: next.placeId,
            ...(session ? { session } : {}),
            radius_km: RADIUS_KM,
          });
          const problem = placeProblem(answer.outcome);
          if (problem) {
            fail(problem);
            return;
          }
          crews = answer.crews;
        }
        saveStart(storage(), next);
        setResults({ kind: "ready", near, crews });
      } catch (error) {
        setResults({ kind: "problem", message: problemOf(error, "We couldn't look for crews just now.") });
      }
    },
    [user],
  );

  useEffect(() => {
    if (!initial) return;
    // Started from a callback, and dropped if the page closes first.
    let current = true;
    void Promise.resolve().then(() => {
      if (current) void look(initial);
    });
    return () => {
      current = false;
    };
  }, [initial, look]);

  function begin(next: Start, session?: string) {
    setStart(next);
    setChoosing(false);
    setResults({ kind: "searching", near: nearOf(next) });
    void look(next, session);
  }

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-5 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <h1 className="text-display-sm leading-tight font-extrabold tracking-[-0.02em] font-display">Find</h1>
      <section aria-labelledby="near-heading" className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <h2 id="near-heading" className="text-title-sm font-extrabold">
            Crews near you
          </h2>
          <p className="text-body text-muted">
            Open crews welcome anyone on Popshot. You see where they play and how many play; you meet the people when
            you join.
          </p>
        </div>

        {choosing ? (
          <ChooseStart
            onStart={(next, session) => {
              begin(next, session);
            }}
            onCancel={
              start
                ? () => {
                    setChoosing(false);
                  }
                : undefined
            }
          />
        ) : (
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-body">
              Near <span className="font-bold">{start?.kind === "place" ? start.label : "you"}</span>
            </p>
            <button
              type="button"
              className={buttonClass("quiet")}
              onClick={() => {
                setChoosing(true);
              }}
            >
              Change
            </button>
          </div>
        )}

        <div aria-live="polite" className="flex flex-col gap-3">
          {results.kind === "searching" && <p className="text-body text-muted">Looking for crews…</p>}
          {results.kind === "problem" && (
            <p role="alert" className="text-body text-warn">
              {results.message}
            </p>
          )}
          {results.kind === "ready" && results.crews.length === 0 && (
            <div className="flex flex-col items-start gap-3 rounded-3xl bg-surface p-5 shadow-card">
              <p className="text-body">No open crews within {RADIUS_KM} km yet.</p>
              <p className="text-small text-muted">Start one, and open it when you&apos;re ready for more players.</p>
              <Link href="/crew" className={buttonClass("quiet")}>
                Start a crew
              </Link>
            </div>
          )}
          {results.kind === "ready" && results.crews.length > 0 && (
            <ul aria-label="Open crews" className="flex flex-col gap-3">
              {results.crews.map((crew) => (
                <li key={crew.group_id}>
                  <CrewCard crew={crew} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </main>
  );
}

function ChooseStart({
  onStart,
  onCancel,
}: {
  onStart: (start: Start, session?: string) => void;
  onCancel?: () => void;
}) {
  const { user } = useSignedIn();
  const [typed, setTyped] = useState("");
  const [found, setFound] = useState<
    | { kind: "idle" }
    | { kind: "searching" }
    | { kind: "ready"; suggestions: PlaceSuggestion[] }
    | { kind: "problem"; message: string }
  >({ kind: "idle" });
  // One Google session from the first keystroke to the pick.
  const session = useRef<string>(newSession());
  const latest = useRef(0);
  const resultsId = useId();

  const query = searchText(typed);
  useEffect(() => {
    if (query === null) return;
    const ask = ++latest.current;
    const timer = window.setTimeout(() => {
      setFound({ kind: "searching" });
      apiPost<SearchResult>(user, "/v1/open-crews/places", { text: query, session: session.current })
        .then((result) => {
          if (ask !== latest.current) return;
          setFound(
            result.unavailable
              ? { kind: "problem", message: "Place search isn't working just now. Try your location instead." }
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
  }, [query, user]);

  return (
    <div className="flex flex-col gap-4 rounded-3xl bg-surface p-5 shadow-card">
      <button
        type="button"
        className={buttonClass("primary", "self-start")}
        onClick={() => {
          onStart({ kind: "here" });
        }}
      >
        Use my location
      </button>
      <p className="text-small text-muted">Used for this search only, never kept.</p>
      <label className="flex flex-col gap-2">
        <span className="text-body font-bold">Or search for a town or park</span>
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
          placeholder="Town, park or club"
          aria-controls={resultsId}
          className={field}
        />
      </label>
      <div id={resultsId} aria-live="polite" className="flex flex-col gap-2">
        {found.kind === "searching" && <p className="text-body text-muted">Searching…</p>}
        {found.kind === "problem" && <p className="text-body text-warn">{found.message}</p>}
        {found.kind === "ready" && found.suggestions.length === 0 && (
          <p className="text-body text-muted">Nothing found. Try another name.</p>
        )}
        {found.kind === "ready" && found.suggestions.length > 0 && (
          <>
            <ul aria-label="Places found" className="flex flex-col gap-2">
              {found.suggestions.map((suggestion) => (
                <li key={suggestion.place_id}>
                  <button
                    type="button"
                    onClick={() => {
                      onStart({ kind: "place", placeId: suggestion.place_id, label: suggestion.main }, session.current);
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
      {onCancel && (
        <button type="button" className={buttonClass("quiet", "self-start")} onClick={onCancel}>
          Cancel
        </button>
      )}
    </div>
  );
}

function CrewCard({ crew }: { crew: OpenCrew }) {
  const headingId = useId();
  const usual = usualLine({ usual_days: crew.usual_days as Day[], usual_times: crew.usual_times as TimeOfDay[] });
  const maps = mapsUrl(crew.google_place_id, crew.court);
  const space = spaceLabel(crew);
  return (
    <article aria-labelledby={headingId} className="flex flex-col gap-3 rounded-3xl bg-surface p-5 shadow-card">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 id={headingId} className="min-w-0 text-title-sm font-extrabold break-words">
          {crew.name}
        </h3>
        <span className="text-meta text-muted tabular-nums">{distanceLabel(crew.distance_km)}</span>
      </div>
      {crew.about && <p className="text-body break-words">{crew.about}</p>}
      <p className="text-body text-muted break-words">
        Plays at <span className="font-bold text-ink">{crew.court}</span>
        {maps && (
          <>
            {" "}
            <a
              href={maps}
              target="_blank"
              rel="noopener noreferrer"
              className="font-bold text-primary"
              aria-label={`Open ${crew.court} in Maps`}
            >
              (Maps ↗)
            </a>
          </>
        )}
      </p>
      {usual && <p className="text-small text-muted">{usual}</p>}
      <p className="text-small font-bold">{space}</p>
      <div className="flex flex-wrap items-center gap-3">
        {crew.my_status === "active" ? (
          <Link href={`/groups/${crew.group_id}`} className={buttonClass("quiet")}>
            You&apos;re in · Open crew
          </Link>
        ) : crew.my_status === "pending" ? (
          <p className="text-body text-muted">Waiting to be let in</p>
        ) : space === "Full" ? (
          <p className="text-body text-muted">Full for now</p>
        ) : (
          <JoinSheet crew={crew} />
        )}
        <ReportSheet crew={crew} />
      </div>
    </article>
  );
}

function JoinSheet({ crew }: { crew: OpenCrew }) {
  const { user } = useSignedIn();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function join() {
    setBusy(true);
    setProblem(null);
    try {
      await apiPost(user, `/v1/open-crews/${crew.group_id}/join`, {});
      setOpen(false);
      router.push(`/groups/${crew.group_id}`);
    } catch (error) {
      setProblem(
        error instanceof ApiError && error.status === 404
          ? "This crew isn't open any more."
          : problemOf(error, "We couldn't join just now. Try again in a moment."),
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet
      trigger={
        <button type="button" className={buttonClass("primary")}>
          Join
        </button>
      }
      open={open}
      onOpenChange={(next) => {
        if (!next) setProblem(null);
        setOpen(next);
      }}
      title={`Join ${crew.name}?`}
      description="You'll be a member straight away."
    >
      <div className="flex flex-col gap-4">
        <ul className="flex list-disc flex-col gap-2 pl-5 text-body">
          <li>Members see your name and photo, and the games you play with them.</li>
          <li>The crew&apos;s leads hear that you joined.</li>
          <li>You can leave any time from the crew&apos;s settings.</li>
        </ul>
        <p role="alert" className="text-body text-warn empty:hidden">
          {problem}
        </p>
        <button
          type="button"
          className={buttonClass("primary", "h-14")}
          disabled={busy}
          onClick={() => {
            void join();
          }}
        >
          {busy ? "Joining…" : "Join crew"}
        </button>
      </div>
    </Sheet>
  );
}

function ReportSheet({ crew }: { crew: OpenCrew }) {
  const { user } = useSignedIn();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState<ReportReason | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const groupName = useId();

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (reason === null) {
      setProblem("Pick a reason.");
      return;
    }
    if (hasLink(note)) {
      setProblem("Leave out links and web or email addresses.");
      return;
    }
    setBusy(true);
    setProblem(null);
    try {
      await apiPost(user, `/v1/open-crews/${crew.group_id}/report`, {
        reason,
        ...(note.trim() ? { note: note.trim() } : {}),
      });
      setSent(true);
    } catch (error) {
      setProblem(problemOf(error, "We couldn't send that just now."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Sheet
      trigger={
        <button type="button" className={buttonClass("quiet")}>
          Report
        </button>
      }
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          setReason(null);
          setNote("");
          setProblem(null);
          setSent(false);
        }
        setOpen(next);
      }}
      title={`Report ${crew.name}`}
      description="Popshot's team looks at every report. The crew doesn't see who sent it."
    >
      {sent ? (
        <p role="status" className="text-body">
          Thanks. We&apos;ll look at it.
        </p>
      ) : (
        <form className="flex flex-col gap-4" onSubmit={(event) => void submit(event)} noValidate>
          <fieldset className="flex flex-col gap-2">
            <legend className="mb-2 text-body font-bold">What&apos;s wrong?</legend>
            {REPORT_REASONS.map((option) => (
              <label key={option.value} className="flex min-h-11 items-center gap-3 text-body">
                <input
                  type="radio"
                  name={groupName}
                  value={option.value}
                  checked={reason === option.value}
                  onChange={() => {
                    setReason(option.value);
                    setProblem(null);
                  }}
                  className="size-5 accent-primary"
                />
                {option.label}
              </label>
            ))}
          </fieldset>
          <label className="flex flex-col gap-2">
            <span className="text-body font-bold">Anything to add? (optional)</span>
            <textarea
              value={note}
              onChange={(event) => {
                setNote(event.target.value);
              }}
              maxLength={300}
              rows={3}
              className="rounded-xl border border-line bg-bg px-4 py-3 text-field text-ink"
            />
          </label>
          <p role="alert" className="text-body text-warn empty:hidden">
            {problem}
          </p>
          <button type="submit" className={buttonClass("primary", "h-14")} disabled={busy}>
            {busy ? "Sending…" : "Send report"}
          </button>
        </form>
      )}
    </Sheet>
  );
}
