"use client";

import { useId } from "react";

import { byArea, toggle, type FocusOption } from "@/lib/focus";

const CHIP = {
  regular: "flex min-h-11 cursor-pointer items-center gap-1.5 rounded-full border-2 px-3.5 text-[15px] font-bold",
  compact: "flex min-h-10 cursor-pointer items-center gap-1 rounded-full border-2 px-3 text-[14px] font-bold",
  on: "border-primary bg-primary text-on-primary",
  off: "border-line bg-bg text-ink disabled:cursor-not-allowed disabled:opacity-45",
};

/**
 * Multi-select from the focus options, as toggle chips grouped by area. Keeps at most `max`
 * picked. `marked` options get a quiet "In your profile" note; `blocked` ones are on the
 * other list here and can't be picked twice.
 */
export function FocusPicker({
  legend,
  hint,
  options,
  selected,
  onChange,
  max,
  marked,
  blocked,
  blockedReason,
  compact = false,
}: {
  legend: string;
  hint?: string;
  options: readonly FocusOption[];
  selected: readonly string[];
  onChange: (next: string[]) => void;
  max: number;
  marked?: ReadonlySet<string>;
  blocked?: ReadonlySet<string>;
  blockedReason?: string;
  // Smaller chips without area headings, for the post-game sheet on a phone.
  compact?: boolean;
}) {
  const id = useId();
  const full = selected.length >= max;
  return (
    <fieldset className="flex flex-col gap-3" aria-describedby={`${id}-count`}>
      <legend className="flex w-full items-baseline justify-between gap-3">
        <span className="text-[17px] font-extrabold">{legend}</span>
      </legend>
      <p id={`${id}-count`} className="-mt-2 text-[14px] text-muted">
        {hint ? `${hint} ` : ""}
        {String(selected.length)} of {String(max)} picked.
      </p>
      <div className={compact ? "flex flex-wrap gap-1.5" : "contents"}>
      {byArea(options).map((group) => (
        <div key={group.area} className={compact ? "contents" : "flex flex-col gap-1.5"}>
          {!compact && <p className="text-[12px] font-bold tracking-[0.08em] text-muted uppercase">{group.area}</p>}
          <div className={compact ? "contents" : "flex flex-wrap gap-2"}>
            {group.options.map((option) => {
              const on = selected.includes(option.id);
              const isBlocked = !on && (blocked?.has(option.id) ?? false);
              const inProfile = marked?.has(option.id) ?? false;
              return (
                <button
                  key={option.id}
                  type="button"
                  aria-pressed={on}
                  disabled={isBlocked || (full && !on)}
                  onClick={() => {
                    onChange(toggle(selected, option.id, max));
                  }}
                  className={`${CHIP[compact ? "compact" : "regular"]} ${on ? CHIP.on : CHIP.off}`}
                >
                  {on && <span aria-hidden="true">✓</span>}
                  {option.label}
                  {isBlocked && blockedReason && <span className="sr-only">({blockedReason})</span>}
                  {inProfile && (
                    <span className={on ? "text-[12px] font-semibold opacity-80" : "text-[12px] font-semibold text-muted"}>
                      · in your profile
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}
      </div>
    </fieldset>
  );
}
