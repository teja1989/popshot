"use client";

import { useRef, useState, type ReactNode, type SubmitEvent } from "react";

import { apiPost, ApiError } from "@/lib/api-client";
import { GROUP_NAME_MAX, type Format, type GroupDetail, type PointsTo } from "@/lib/groups";

import { useSignedIn } from "./auth";
import { buttonClass } from "./ui/button";
import { segmentOption } from "./ui/segmented";
import { Sheet } from "./ui/sheet";

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
  const [format, setFormat] = useState<Format>("doubles");
  const [pointsTo, setPointsTo] = useState<PointsTo>(11);
  const [winByTwo, setWinByTwo] = useState(true);
  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  function reset() {
    setName("");
    setFormat("doubles");
    setPointsTo(11);
    setWinByTwo(true);
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
        default_format: format,
        default_points_to: pointsTo,
        default_win_by_two: winByTwo,
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

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-2 text-[15px] font-bold">Usual format</legend>
          <div className="grid grid-cols-2 gap-1 rounded-xl bg-chip p-1">
            {(["doubles", "singles"] as const).map((value) => (
              <label key={value} className={segmentOption}>
                <input
                  type="radio"
                  name="format"
                  value={value}
                  checked={format === value}
                  onChange={() => {
                    setFormat(value);
                  }}
                  className="sr-only"
                />
                {value === "doubles" ? "Doubles" : "Singles"}
              </label>
            ))}
          </div>
        </fieldset>

        <div className="flex flex-wrap items-end justify-between gap-4">
          <fieldset>
            <legend className="mb-2 text-[15px] font-bold">Games to</legend>
            <div className="grid grid-cols-3 gap-1 rounded-xl bg-chip p-1">
              {([11, 15, 21] as const).map((value) => (
                <label key={value} className={`${segmentOption} w-12`}>
                  <input
                    type="radio"
                    name="points_to"
                    value={value}
                    checked={pointsTo === value}
                    onChange={() => {
                      setPointsTo(value);
                    }}
                    className="sr-only"
                  />
                  {value}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="flex min-h-11 cursor-pointer items-center gap-3 text-[15px] font-bold">
            <input
              type="checkbox"
              role="switch"
              checked={winByTwo}
              onChange={(event) => {
                setWinByTwo(event.target.checked);
              }}
              className="relative h-[26px] w-11 cursor-pointer appearance-none rounded-full bg-line transition-colors duration-200 before:absolute before:top-[3px] before:left-[3px] before:size-5 before:rounded-full before:bg-surface before:shadow-sm before:transition-transform before:duration-200 before:ease-court checked:bg-primary checked:before:translate-x-[18px]"
            />
            Win by 2
          </label>
        </div>
        <p className="-mt-2 text-[14px] text-muted">
          These are the starting choices when someone logs a game. They can change them each time.
        </p>

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
