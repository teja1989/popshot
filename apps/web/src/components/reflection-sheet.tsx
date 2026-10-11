"use client";

import { useState, type ReactNode } from "react";

import { apiPut, ApiError } from "@/lib/api-client";
import { MAX_PER_REFLECTION, type Focus, type FocusOption, type Reflection } from "@/lib/focus";
import { namesOn, scoreLine, type Match } from "@/lib/games";

import { useSignedIn } from "./auth";
import { FocusPicker } from "./focus-picker";
import { useApiGet } from "./use-api";
import { buttonClass } from "./ui/button";
import { Sheet } from "./ui/sheet";

/**
 * "How did it go?" after a game you played. Optional: closing it changes nothing (the game
 * keeps its prompt for a few days), "Skip this game" stops the prompt, and Save keeps your
 * picks. Your profile's Strengths and Areas are marked, never pre-picked.
 */
export function ReflectionSheet({
  groupId,
  match,
  open,
  onOpenChange,
  onSaved,
  trigger,
}: {
  groupId: string;
  match: Match;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: (reflection: Reflection) => void;
  trigger?: ReactNode;
}) {
  return (
    <Sheet
      trigger={trigger}
      open={open}
      onOpenChange={onOpenChange}
      title="How did it go?"
      description={`${namesOn(match, match.winner)} won ${scoreLine(match)}. Just for you: nobody else sees this.`}
    >
      {open && <ReflectionForm groupId={groupId} match={match} onSaved={onSaved} />}
    </Sheet>
  );
}

function ReflectionForm({ groupId, match, onSaved }: { groupId: string; match: Match; onSaved: (reflection: Reflection) => void }) {
  const { user } = useSignedIn();
  const options = useApiGet<FocusOption[]>("/v1/focus-options");
  const focus = useApiGet<Focus>("/v1/me/focus");
  const [wentWell, setWentWell] = useState<string[]>(match.my_reflection?.went_well ?? []);
  const [toImprove, setToImprove] = useState<string[]>(match.my_reflection?.to_improve ?? []);
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function save(reflection: Reflection) {
    setSaving(true);
    setProblem(null);
    try {
      onSaved(await apiPut<Reflection>(user, `/v1/groups/${groupId}/matches/${match.id}/reflection`, reflection));
    } catch (error) {
      setProblem(error instanceof ApiError && error.detail ? error.detail : "We couldn't save that just now.");
      setSaving(false);
    }
  }

  if (options.result.kind === "loading") {
    return <p className="text-muted">Loading…</p>;
  }
  if (options.result.kind === "error") {
    return (
      <div role="alert" className="flex flex-col items-start gap-3">
        <p>We couldn&apos;t load the options just now.</p>
        <button type="button" className={buttonClass("quiet")} onClick={options.reload}>
          Try again
        </button>
      </div>
    );
  }
  // Without your profile the picker still works; the "in your profile" marks just don't show.
  const profile = focus.result.kind === "ready" ? focus.result.data : null;

  return (
    <div className="flex flex-col gap-5">
      <FocusPicker
        legend="What went well?"
        hint={`Up to ${String(MAX_PER_REFLECTION)}.`}
        options={options.result.data}
        selected={wentWell}
        onChange={setWentWell}
        max={MAX_PER_REFLECTION}
        marked={new Set(profile?.strengths ?? [])}
        blocked={new Set(toImprove)}
        blockedReason="picked under what to improve"
        compact
      />
      <FocusPicker
        legend="What to improve?"
        hint={`Up to ${String(MAX_PER_REFLECTION)}.`}
        options={options.result.data}
        selected={toImprove}
        onChange={setToImprove}
        max={MAX_PER_REFLECTION}
        marked={new Set(profile?.improve ?? [])}
        blocked={new Set(wentWell)}
        blockedReason="picked under what went well"
        compact
      />
      <p role="alert" className="text-[15px] text-warn empty:hidden">
        {problem}
      </p>
      {/* Pinned to the bottom of the sheet so Save is never a scroll away. */}
      <div className="sticky -bottom-8 -mx-5 grid grid-cols-2 gap-2 border-t border-line bg-surface px-5 pt-3 pb-8 sm:-bottom-6 sm:pb-6">
        <button
          type="button"
          className={buttonClass("primary", "h-14")}
          disabled={saving || (wentWell.length === 0 && toImprove.length === 0)}
          onClick={() => void save({ went_well: wentWell, to_improve: toImprove })}
        >
          {saving ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          className={buttonClass("quiet", "h-14")}
          disabled={saving}
          onClick={() => void save({ went_well: [], to_improve: [] })}
        >
          Skip this game
        </button>
      </div>
    </div>
  );
}
