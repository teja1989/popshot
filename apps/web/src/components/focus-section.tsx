"use client";

import { useState } from "react";

import { apiPut, ApiError } from "@/lib/api-client";
import { describeSuggestion, labelFor, MAX_IMPROVE, MAX_STRENGTHS, promote, type Focus, type FocusOption, type Suggestion } from "@/lib/focus";

import { useSignedIn } from "./auth";
import { FocusPicker } from "./focus-picker";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";
import { LockIcon } from "./ui/icons";
import { Sheet } from "./ui/sheet";

/** Your Strengths and Areas to improve, with suggestions from your reflections. Private. */
export function FocusSection() {
  const options = useApiGet<FocusOption[]>("/v1/focus-options");
  const focus = useApiGet<Focus>("/v1/me/focus");

  return (
    <section aria-labelledby="focus-heading" className="flex animate-rise flex-col gap-3 [animation-delay:40ms]">
      <div className="flex items-center justify-between gap-3">
        <h2 id="focus-heading" className="text-xs font-bold tracking-[0.1em] text-muted uppercase">
          Your game
        </h2>
        <span className="flex items-center gap-1.5 text-[13px] text-muted">
          <LockIcon />
          Only you can see this
        </span>
      </div>
      {(options.result.kind === "loading" || focus.result.kind === "loading") && <p className="text-muted">Loading…</p>}
      {(options.result.kind === "error" || focus.result.kind === "error") && (
        <div role="alert" className="flex flex-col items-start gap-3 rounded-2xl border border-line bg-surface p-5">
          <p>We couldn&apos;t load this just now.</p>
          <button
            type="button"
            className={buttonClass("quiet")}
            onClick={() => {
              options.reload();
              focus.reload();
            }}
          >
            Try again
          </button>
        </div>
      )}
      {options.result.kind === "ready" && focus.result.kind === "ready" && (
        <FocusCard options={options.result.data} focus={focus.result.data} onSaved={focus.replace} />
      )}
    </section>
  );
}

function Chips({ ids, options, empty }: { ids: string[]; options: FocusOption[]; empty: string }) {
  if (ids.length === 0) {
    return <p className="text-[15px] text-muted">{empty}</p>;
  }
  return (
    <ul className="flex flex-wrap gap-2">
      {ids.map((id) => (
        <li key={id} className="rounded-full bg-chip px-3 py-1.5 text-[14px] font-bold">
          {labelFor(options, id)}
        </li>
      ))}
    </ul>
  );
}

function FocusCard({ options, focus, onSaved }: { options: FocusOption[]; focus: Focus; onSaved: (focus: Focus) => void }) {
  const { user } = useSignedIn();
  const [problem, setProblem] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function accept(suggestion: Suggestion) {
    const next = promote(focus, suggestion);
    if (!next) {
      setProblem(
        suggestion.kind === "strength"
          ? `You already have ${String(MAX_STRENGTHS)} strengths. Edit them to make room.`
          : `You already have ${String(MAX_IMPROVE)} areas to improve. Edit them to make room.`,
      );
      return;
    }
    setBusy(true);
    setProblem(null);
    try {
      onSaved(await apiPut<Focus>(user, "/v1/me/focus", next));
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "We couldn't save that just now.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 rounded-2xl border border-line bg-surface p-5">
      <div className="flex flex-col gap-2">
        <h3 className="text-[16px] font-extrabold">Strengths</h3>
        <Chips ids={focus.strengths} options={options} empty="Nothing picked yet." />
      </div>
      <div className="flex flex-col gap-2">
        <h3 className="text-[16px] font-extrabold">Areas to improve</h3>
        <Chips ids={focus.improve} options={options} empty="Nothing picked yet." />
      </div>
      <EditFocusSheet options={options} focus={focus} onSaved={onSaved} />

      {focus.suggestions.length > 0 && (
        <div className="flex flex-col gap-3 border-t border-line pt-4">
          <h3 className="text-[16px] font-extrabold">From your post-game notes</h3>
          <ul className="flex flex-col gap-3">
            {focus.suggestions.map((s) => {
              const label = labelFor(options, s.option_id);
              return (
                <li key={`${s.kind}-${s.option_id}`} className="flex flex-col gap-2 rounded-xl bg-chip p-3">
                  <p className="text-[15px]">{describeSuggestion(s, label)}</p>
                  <button
                    type="button"
                    className={buttonClass("quiet", "min-h-11 self-start bg-surface px-4 text-[15px]")}
                    disabled={busy}
                    onClick={() => void accept(s)}
                  >
                    {s.kind === "strength" ? "Add to Strengths" : "Add to Areas to improve"}
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      )}
      <p role="alert" className="text-[15px] text-warn empty:hidden">
        {problem}
      </p>
    </div>
  );
}

function EditFocusSheet({ options, focus, onSaved }: { options: FocusOption[]; focus: Focus; onSaved: (focus: Focus) => void }) {
  const { user } = useSignedIn();
  const [open, setOpen] = useState(false);
  const [strengths, setStrengths] = useState<string[]>(focus.strengths);
  const [improve, setImprove] = useState<string[]>(focus.improve);
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function save() {
    setSaving(true);
    setProblem(null);
    try {
      onSaved(await apiPut<Focus>(user, "/v1/me/focus", { strengths, improve }));
      setOpen(false);
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "We couldn't save that just now.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet
      trigger={
        <button type="button" className={buttonClass("quiet", "min-h-11 self-start px-4 text-[15px]")}>
          Edit your game
        </button>
      }
      open={open}
      onOpenChange={(next) => {
        if (next) {
          setStrengths(focus.strengths);
          setImprove(focus.improve);
          setProblem(null);
        }
        setOpen(next);
      }}
      title="Your game"
      description="Your own notes on your game. Only you can see them."
    >
      <div className="flex flex-col gap-6">
        <FocusPicker
          legend="Strengths"
          hint={`Up to ${String(MAX_STRENGTHS)}.`}
          options={options}
          selected={strengths}
          onChange={setStrengths}
          max={MAX_STRENGTHS}
          blocked={new Set(improve)}
          blockedReason="in Areas to improve"
        />
        <FocusPicker
          legend="Areas to improve"
          hint={`Up to ${String(MAX_IMPROVE)}.`}
          options={options}
          selected={improve}
          onChange={setImprove}
          max={MAX_IMPROVE}
          blocked={new Set(strengths)}
          blockedReason="in Strengths"
        />
        <p role="alert" className="text-[15px] text-warn empty:hidden">
          {problem}
        </p>
        <button type="button" className={buttonClass("primary", "h-14 w-full")} disabled={saving} onClick={() => void save()}>
          {saving ? "Saving…" : "Save"}
        </button>
      </div>
    </Sheet>
  );
}
