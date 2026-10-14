"use client";

import Link from "next/link";
import { useId, useState, type SubmitEvent } from "react";

import { apiDelete, apiPost, ApiError } from "@/lib/api-client";
import { labelFor, type Focus, type FocusOption } from "@/lib/focus";
import {
  COPY,
  FEATURE,
  localDate,
  NOTE_MAX,
  QUESTIONS,
  tipFor,
  workingOn,
  type Journey,
  type LearningNote,
  type Story,
} from "@/lib/journey";

import { pickAction, pickForDay, type Pick } from "@/lib/library";

import { useSignedIn } from "./auth";
import { useFeaturesLoaded, useYouFeature } from "./features";
import { StorySheet } from "./story-sheet";
import { useApiGet } from "./use-api";
import { YouTabs } from "./you-tabs";
import { buttonClass } from "./ui/button";
import { CloseIcon, LockIcon } from "./ui/icons";

const CARD = "flex flex-col gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-5";
const MAIN = "mx-auto flex w-full max-w-md flex-col gap-6 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10";

/** The Journey tab of You: your story, a tip a day, and what you're learning. Yours alone. */
export function JourneyView() {
  const loaded = useFeaturesLoaded();
  const on = useYouFeature(FEATURE);
  if (!loaded) {
    return (
      <main className={MAIN}>
        <p className="text-muted">Loading…</p>
      </main>
    );
  }
  if (!on) {
    return (
      <main className={MAIN}>
        <h1 className="text-title-lg leading-tight font-extrabold font-display">{COPY.title}</h1>
        <p className="text-body text-muted">{COPY.off}</p>
        <Link href="/you" className={buttonClass("quiet", "min-h-11 self-start px-4 text-body")}>
          Back to You
        </Link>
      </main>
    );
  }
  return <JourneyPage />;
}

function JourneyPage() {
  const journey = useApiGet<Journey>("/v1/me/journey");
  const options = useApiGet<FocusOption[]>("/v1/focus-options");
  const focus = useApiGet<Focus>("/v1/me/focus");

  const ready = journey.result.kind === "ready" && options.result.kind === "ready";
  const failed = journey.result.kind === "error" || options.result.kind === "error";

  return (
    <main className={MAIN}>
      <YouTabs />
      <header className="flex animate-rise flex-col gap-1">
        <div className="flex items-center justify-between gap-3">
          <h1 className="text-display-sm leading-tight font-extrabold tracking-[-0.02em] font-display">{COPY.title}</h1>
          <span className="flex items-center gap-1.5 text-meta text-muted">
            <LockIcon />
            Only you can see this
          </span>
        </div>
        <p className="text-body text-muted">{COPY.motto}</p>
      </header>

      {!ready && !failed && <p className="text-muted">Loading…</p>}
      {failed && (
        <div role="alert" className={`${CARD} items-start`}>
          <p>We couldn&apos;t load this just now.</p>
          <button
            type="button"
            className={buttonClass("quiet")}
            onClick={() => {
              journey.reload();
              options.reload();
            }}
          >
            Try again
          </button>
        </div>
      )}
      {journey.result.kind === "ready" && options.result.kind === "ready" && (
        <JourneyBody
          journey={journey.result.data}
          options={options.result.data}
          improve={focus.result.kind === "ready" ? focus.result.data.improve : []}
          onChange={journey.replace}
          reload={journey.reload}
        />
      )}
    </main>
  );
}

function JourneyBody({
  journey,
  options,
  improve,
  onChange,
  reload,
}: {
  journey: Journey;
  options: FocusOption[];
  improve: string[];
  onChange: (journey: Journey) => void;
  reload: () => void;
}) {
  const skills = workingOn(journey.story, improve);
  const tip = tipFor(skills, new Date());
  return (
    <>
      <p className="flex animate-rise flex-col self-start rounded-2xl bg-secondary-container px-4 py-3 text-on-secondary-container [animation-delay:60ms]">
        <span className="text-title-sm font-extrabold font-numeral" data-learning-days>
          {COPY.learningDays(journey.learning_days)}
        </span>
        <span className="text-small">{COPY.learningDaysHint}</span>
      </p>

      <section aria-labelledby="today-heading" className={`${CARD} animate-rise [animation-delay:120ms]`}>
        <h2 id="today-heading" className="text-title-sm font-bold">
          {COPY.todayHeading}
        </h2>
        {tip.skill && (
          <p className="self-start rounded-full bg-chip px-3 py-1 text-small font-bold">
            {labelFor(options, tip.skill)}
          </p>
        )}
        <p className="text-lead">{tip.text}</p>
        <TodayPick skills={skills} />
      </section>

      <NotesSection journey={journey} options={options} onChange={onChange} reload={reload} />

      <StorySection journey={journey} options={options} onChange={onChange} />

      <section aria-labelledby="checkins-heading" className="flex animate-rise flex-col gap-2 [animation-delay:300ms]">
        <h2 id="checkins-heading" className="text-title-sm font-bold">
          {COPY.checkinsHeading}
        </h2>
        <p className="rounded-2xl border border-dashed border-line p-4 text-body text-muted">{COPY.checkinsSoon}</p>
      </section>
    </>
  );
}

/** One video or article from the library for the skills you're working on, if there is one. */
function TodayPick({ skills }: { skills: string[] }) {
  const query = skills.map((s) => `skills=${encodeURIComponent(s)}`).join("&");
  const picks = useApiGet<Pick[]>(`/v1/me/journey/picks${query ? `?${query}` : ""}`);
  const pick = picks.result.kind === "ready" ? pickForDay(picks.result.data, new Date()) : null;
  if (!pick) {
    return null;
  }
  return (
    <a
      href={pick.url}
      target="_blank"
      rel="noopener noreferrer"
      className="pressable flex items-center gap-3 rounded-2xl bg-surface-low p-3 text-ink no-underline"
      data-today-pick
    >
      <span className="flex min-w-0 grow flex-col">
        <span className="text-body font-bold break-words">{pick.title}</span>
        <span className="text-small text-muted">{pick.source}</span>
      </span>
      <span className="shrink-0 rounded-full bg-primary px-3 py-1.5 text-small font-bold text-on-primary">
        {pickAction(pick)}
      </span>
    </a>
  );
}

function NotesSection({
  journey,
  options,
  onChange,
  reload,
}: {
  journey: Journey;
  options: FocusOption[];
  onChange: (journey: Journey) => void;
  reload: () => void;
}) {
  const { user } = useSignedIn();
  const id = useId();
  const [body, setBody] = useState("");
  const [skill, setSkill] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const skills = journey.story ? [...journey.story.tag_gaps, ...journey.story.tag_strengths] : [];

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!body.trim()) {
      setProblem("Write a few words first.");
      return;
    }
    setSaving(true);
    setProblem(null);
    try {
      await apiPost<LearningNote>(user, "/v1/me/journey/notes", {
        body,
        skill,
        noted_on: localDate(new Date()),
      });
      setBody("");
      setSkill(null);
      // The note may add a learning day: read the journey again.
      reload();
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "We couldn't save that just now.");
    } finally {
      setSaving(false);
    }
  }

  async function remove(note: LearningNote) {
    setProblem(null);
    try {
      await apiDelete(user, `/v1/me/journey/notes/${note.id}`);
      onChange({ ...journey, notes: journey.notes.filter((n) => n.id !== note.id) });
      reload();
    } catch {
      setProblem("We couldn't delete that just now.");
    }
  }

  return (
    <section aria-labelledby="notes-heading" className={`${CARD} animate-rise [animation-delay:180ms]`}>
      <h2 id="notes-heading" className="text-title-sm font-bold">
        {COPY.noteHeading}
      </h2>
      <form className="flex flex-col gap-2" onSubmit={(event) => void submit(event)} noValidate>
        <label htmlFor={`${id}-note`} className="sr-only">
          {COPY.noteHeading}
        </label>
        <textarea
          id={`${id}-note`}
          rows={2}
          maxLength={NOTE_MAX}
          value={body}
          placeholder={COPY.notePlaceholder}
          aria-describedby={`${id}-count`}
          onChange={(event) => {
            setBody(event.target.value);
          }}
          className="rounded-xl border border-line bg-bg px-4 py-3 text-field text-ink"
        />
        <span id={`${id}-count`} className="self-end text-meta text-muted">
          {body.length}/{NOTE_MAX}
        </span>
        {skills.length > 0 && (
          <fieldset className="flex flex-col gap-1.5">
            <legend className="mb-1.5 text-small font-bold">About a skill? (optional)</legend>
            <div className="flex flex-wrap gap-1.5">
              {skills.map((s) => (
                <button
                  key={s}
                  type="button"
                  aria-pressed={skill === s}
                  onClick={() => {
                    setSkill(skill === s ? null : s);
                  }}
                  className="min-h-10 cursor-pointer rounded-full border-2 border-line px-3 text-small font-bold aria-pressed:border-primary aria-pressed:bg-primary aria-pressed:text-on-primary"
                >
                  {labelFor(options, s)}
                </button>
              ))}
            </div>
          </fieldset>
        )}
        <p role="alert" className="text-body text-warn empty:hidden">
          {problem}
        </p>
        <button
          type="submit"
          className={buttonClass("primary", "min-h-11 self-start px-5 text-body")}
          disabled={saving}
        >
          {saving ? "Saving…" : "Save note"}
        </button>
      </form>

      {journey.notes.length > 0 && (
        <ul className="flex flex-col gap-2 border-t border-line pt-3" aria-label="Your learning notes">
          {journey.notes.map((note) => (
            <li key={note.id} className="flex items-start gap-3 rounded-xl bg-surface-low p-3">
              <div className="flex min-w-0 grow flex-col gap-0.5">
                <p className="text-body break-words">{note.body}</p>
                <p className="text-meta text-muted">
                  {formatDay(note.noted_on)}
                  {note.skill ? ` · ${labelFor(options, note.skill)}` : ""}
                </p>
              </div>
              <button
                type="button"
                aria-label={`Delete note: ${note.body}`}
                onClick={() => void remove(note)}
                className="flex size-11 shrink-0 cursor-pointer items-center justify-center rounded-full text-muted hover:bg-surface-high"
              >
                <CloseIcon />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function StorySection({
  journey,
  options,
  onChange,
}: {
  journey: Journey;
  options: FocusOption[];
  onChange: (journey: Journey) => void;
}) {
  const [open, setOpen] = useState(false);
  const story = journey.story;
  return (
    <section aria-labelledby="story-heading" className={`${CARD} animate-rise [animation-delay:240ms]`}>
      <h2 id="story-heading" className="text-title-sm font-bold">
        {COPY.storyHeading}
      </h2>
      {story ? (
        <StoryText story={story} options={options} />
      ) : (
        <p className="text-body text-muted">{COPY.storyEmpty}</p>
      )}
      <StorySheet
        story={story}
        open={open}
        onOpenChange={setOpen}
        onSaved={onChange}
        trigger={
          <button
            type="button"
            className={buttonClass(story ? "quiet" : "primary", "min-h-11 self-start px-5 text-body")}
          >
            {story ? COPY.storyEdit : COPY.storyStart}
          </button>
        }
      />
      {journey.history.length > 0 && (
        <details className="border-t border-line pt-3">
          <summary className="min-h-11 cursor-pointer content-center text-body font-bold">
            {COPY.earlier(journey.history.length)}
          </summary>
          <ol className="mt-2 flex flex-col gap-3">
            {journey.history.map((old) => (
              <li key={old.id} className="flex flex-col gap-2 rounded-xl bg-surface-low p-3">
                <p className="text-meta font-bold text-muted">{formatDay(old.created_at)}</p>
                <StoryText story={old} options={options} />
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  );
}

function StoryText({ story, options }: { story: Story; options: FocusOption[] }) {
  const skills = [...story.tag_strengths, ...story.tag_gaps];
  return (
    <div className="flex flex-col gap-3">
      <dl className="flex flex-col gap-3">
        {QUESTIONS.filter((q) => story[q.key].trim() !== "").map((q) => (
          <div key={q.key} className="flex flex-col gap-0.5">
            <dt className="text-small font-bold text-muted">{q.label}</dt>
            <dd className="text-body whitespace-pre-line break-words">{story[q.key]}</dd>
          </div>
        ))}
      </dl>
      {skills.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <p className="text-small font-bold text-muted">{COPY.readAs}</p>
          <ul className="flex flex-wrap gap-1.5">
            {story.tag_strengths.map((s) => (
              <li key={`s-${s}`} className="rounded-full bg-chip px-3 py-1 text-small font-bold">
                {labelFor(options, s)}
              </li>
            ))}
            {story.tag_gaps.map((s) => (
              <li
                key={`g-${s}`}
                className="rounded-full bg-secondary-container px-3 py-1 text-small font-bold text-on-secondary-container"
              >
                Working on: {labelFor(options, s)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function formatDay(value: string): string {
  // A plain date (YYYY-MM-DD) is a calendar day; read it as local, not UTC midnight.
  const date = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T12:00:00`) : new Date(value);
  return date.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
}
