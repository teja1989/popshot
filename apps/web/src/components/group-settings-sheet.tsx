"use client";

import { useRef, useState, type SubmitEvent } from "react";

import { apiPatch, ApiError } from "@/lib/api-client";
import { GROUP_NAME_MAX, type GroupDetail } from "@/lib/groups";

import { useSignedIn } from "./auth";
import { GroupRulesFields, type Rules } from "./group-rules-fields";
import { buttonClass } from "./ui/button";
import { Sheet } from "./ui/sheet";

function rulesOf(group: GroupDetail): Rules {
  return { format: group.default_format, pointsTo: group.default_points_to, winByTwo: group.default_win_by_two };
}

/** The group's name and usual rules, for its lead and co-leads. */
export function GroupSettingsSheet({ group, onSaved }: { group: GroupDetail; onSaved: (group: GroupDetail) => void }) {
  const { user } = useSignedIn();
  const [open, setOpen] = useState(false);
  const nameRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState(group.name);
  const [rules, setRules] = useState<Rules>(() => rulesOf(group));
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) {
      setProblem("Give your group a name.");
      nameRef.current?.focus();
      return;
    }
    setSaving(true);
    setProblem(null);
    try {
      const saved = await apiPatch<GroupDetail>(user, `/v1/groups/${group.id}`, {
        name,
        default_format: rules.format,
        default_points_to: rules.pointsTo,
        default_win_by_two: rules.winByTwo,
      });
      setOpen(false);
      onSaved(saved);
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        setProblem("That name won't work. Use letters, numbers, spaces and punctuation.");
      } else if (error instanceof ApiError && error.detail) {
        setProblem(error.detail);
      } else {
        setProblem("We couldn't save that just now. Try again in a moment.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet
      trigger={
        <button type="button" className={buttonClass("quiet", "min-h-11 px-4 text-[15px]")}>
          Group settings
        </button>
      }
      open={open}
      onOpenChange={(next) => {
        if (next) {
          // Start from what's saved now, not from an earlier edit that was closed unsaved.
          setName(group.name);
          setRules(rulesOf(group));
          setProblem(null);
        }
        setOpen(next);
      }}
      title="Group settings"
      description="Leads and co-leads can change these."
    >
      <form className="flex flex-col gap-5" onSubmit={(event) => void submit(event)} noValidate>
        <label className="flex flex-col gap-2">
          <span className="text-[15px] font-bold">Group name</span>
          <input
            ref={nameRef}
            name="name"
            value={name}
            onChange={(event) => {
              setName(event.target.value);
            }}
            maxLength={GROUP_NAME_MAX}
            autoComplete="off"
            aria-invalid={problem ? true : undefined}
            aria-describedby={problem ? "group-settings-problem" : undefined}
            className="min-h-12 rounded-xl border border-line bg-bg px-4 text-[17px] text-ink"
          />
        </label>
        <GroupRulesFields rules={rules} onChange={setRules} />
        <p id="group-settings-problem" role="alert" className="min-h-6 text-[15px] text-warn">
          {problem}
        </p>
        <button type="submit" className={buttonClass("primary", "h-14 w-full")} disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
      </form>
    </Sheet>
  );
}
