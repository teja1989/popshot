"use client";

import { useId, useState, type ReactNode, type SubmitEvent } from "react";

import { apiPut, ApiError } from "@/lib/api-client";
import type { FocusOption } from "@/lib/focus";
import {
  COPY,
  emptyDraft,
  hasWords,
  MAX_TAGS,
  QUESTIONS,
  STORY_LIMITS,
  type Journey,
  type Story,
  type StoryDraft,
} from "@/lib/journey";

import { useSignedIn } from "./auth";
import { FocusPicker } from "./focus-picker";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";
import { Sheet } from "./ui/sheet";

/**
 * Write or update your story: four questions in your own words, and the skills you'd name.
 * Each save is a new version; the earlier ones are kept. Full screen on phones, for typing.
 */
export function StorySheet({
  story,
  trigger,
  open,
  onOpenChange,
  onSaved,
}: {
  story: Story | null;
  trigger?: ReactNode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (journey: Journey) => void;
}) {
  const { user } = useSignedIn();
  const options = useApiGet<FocusOption[]>("/v1/focus-options");
  const [draft, setDraft] = useState<StoryDraft>(() => emptyDraft(story));
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const id = useId();

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    event.stopPropagation();
    if (!hasWords(draft)) {
      setProblem("Write a few words in any of the boxes first.");
      return;
    }
    setSaving(true);
    setProblem(null);
    try {
      // No skills picked: the API takes them from your focus lists instead.
      const { tag_strengths, tag_gaps, ...words } = draft;
      const body = tag_strengths.length + tag_gaps.length > 0 ? draft : words;
      onSaved(await apiPut<Journey>(user, "/v1/me/journey/story", body));
      onOpenChange(false);
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "We couldn't save that just now.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet
      trigger={trigger}
      open={open}
      onOpenChange={(next) => {
        if (next) {
          setDraft(emptyDraft(story));
          setProblem(null);
        }
        onOpenChange(next);
      }}
      title={COPY.storyHeading}
      description={COPY.storySheetDescription}
      fullOnPhone
    >
      <form className="flex flex-col gap-6" onSubmit={(event) => void submit(event)} noValidate>
        {QUESTIONS.map((question) => {
          const value = draft[question.key];
          const max = STORY_LIMITS[question.key];
          return (
            <label key={question.key} className="flex flex-col gap-1.5">
              <span className="text-lead font-extrabold">{question.label}</span>
              <span id={`${id}-${question.key}-hint`} className="text-small text-muted">
                {question.hint}
              </span>
              <textarea
                name={question.key}
                rows={question.key === "origin" ? 4 : 3}
                maxLength={max}
                value={value}
                aria-describedby={`${id}-${question.key}-hint ${id}-${question.key}-count`}
                onChange={(event) => {
                  setDraft({ ...draft, [question.key]: event.target.value });
                }}
                className="rounded-xl border border-line bg-bg px-4 py-3 text-field text-ink"
              />
              <span id={`${id}-${question.key}-count`} className="self-end text-meta text-muted">
                {value.length}/{max}
              </span>
            </label>
          );
        })}

        {options.result.kind === "ready" && (
          <>
            <FocusPicker
              legend="Skills you're good at"
              hint={`Up to ${String(MAX_TAGS)}.`}
              options={options.result.data}
              selected={draft.tag_strengths}
              onChange={(next) => {
                setDraft({ ...draft, tag_strengths: next });
              }}
              max={MAX_TAGS}
              blocked={new Set(draft.tag_gaps)}
              blockedReason="in skills to work on"
              compact
            />
            <FocusPicker
              legend="Skills to work on"
              hint={`Up to ${String(MAX_TAGS)}. Your daily tip comes from these.`}
              options={options.result.data}
              selected={draft.tag_gaps}
              onChange={(next) => {
                setDraft({ ...draft, tag_gaps: next });
              }}
              max={MAX_TAGS}
              blocked={new Set(draft.tag_strengths)}
              blockedReason="in skills you're good at"
              compact
            />
          </>
        )}

        <p role="alert" className="text-body text-warn empty:hidden">
          {problem}
        </p>
        <button type="submit" className={buttonClass("primary", "h-14 w-full")} disabled={saving}>
          {saving ? "Saving…" : "Save your story"}
        </button>
      </form>
    </Sheet>
  );
}
