"use client";

import { useRef, useState, type ReactNode, type SubmitEvent } from "react";

import { apiPost, ApiError } from "@/lib/api-client";
import { GROUP_NAME_MAX, type GroupDetail } from "@/lib/groups";

import { useSignedIn } from "./auth";
import { GroupRulesFields, type Rules } from "./group-rules-fields";
import { buttonClass } from "./ui/button";
import { Sheet } from "./ui/sheet";

const DEFAULT_RULES: Rules = { format: "doubles", pointsTo: 11, winByTwo: true };

export function CreateGroupDialog({
  trigger,
  onCreated,
}: {
  trigger: ReactNode;
  onCreated: (group: GroupDetail) => void;
}) {
  const { user } = useSignedIn();
  const [open, setOpen] = useState(false);
  const nameRef = useRef<HTMLInputElement>(null);
  const [name, setName] = useState("");
  const [rules, setRules] = useState<Rules>(DEFAULT_RULES);
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  function reset() {
    setName("");
    setRules(DEFAULT_RULES);
    setProblem(null);
  }

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
      const group = await apiPost<GroupDetail>(user, "/v1/groups", {
        name,
        default_format: rules.format,
        default_points_to: rules.pointsTo,
        default_win_by_two: rules.winByTwo,
      });
      reset();
      setOpen(false);
      onCreated(group);
    } catch (error) {
      if (error instanceof ApiError && error.status === 422) {
        setProblem("That name won't work. Use letters, numbers, spaces and punctuation.");
      } else if (error instanceof ApiError && error.detail) {
        setProblem(error.detail);
      } else {
        setProblem("We couldn't create the group just now. Try again in a moment.");
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <Sheet
      trigger={trigger}
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          reset();
        }
        setOpen(next);
      }}
      title="Start a group"
      description="You'll be its lead. Invite your crew once it's set up."
      onOpenAutoFocus={(event) => {
        event.preventDefault();
        nameRef.current?.focus();
      }}
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
            placeholder="Tuesday Dinkers"
            aria-invalid={problem ? true : undefined}
            aria-describedby={problem ? "create-group-problem" : undefined}
            className="min-h-12 rounded-xl border border-line bg-bg px-4 text-[17px] text-ink placeholder:text-muted"
          />
        </label>

        <GroupRulesFields rules={rules} onChange={setRules} />

        <p id="create-group-problem" role="alert" className="min-h-6 text-[15px] text-warn">
          {problem}
        </p>
        <button type="submit" className={buttonClass("primary", "h-14 w-full")} disabled={saving}>
          {saving ? "Creating…" : "Create group"}
        </button>
      </form>
    </Sheet>
  );
}
