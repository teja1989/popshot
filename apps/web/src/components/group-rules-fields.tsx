"use client";

import type { Format, PointsTo } from "@/lib/groups";

import { segmentOption } from "./ui/segmented";

export interface Rules {
  format: Format;
  pointsTo: PointsTo;
  winByTwo: boolean;
}

/** A group's usual format, game length and win-by-2: the starting choices when logging a game. */
export function GroupRulesFields({ rules, onChange }: { rules: Rules; onChange: (rules: Rules) => void }) {
  return (
    <>
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-body font-bold">Usual format</legend>
        <div className="grid grid-cols-2 gap-1 rounded-xl bg-chip p-1">
          {(["doubles", "singles"] as const).map((value) => (
            <label key={value} className={segmentOption}>
              <input
                type="radio"
                name="format"
                value={value}
                checked={rules.format === value}
                onChange={() => {
                  onChange({ ...rules, format: value });
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
          <legend className="mb-2 text-body font-bold">Games to</legend>
          <div className="grid grid-cols-3 gap-1 rounded-xl bg-chip p-1">
            {([11, 15, 21] as const).map((value) => (
              <label key={value} className={`${segmentOption} w-12`}>
                <input
                  type="radio"
                  name="points_to"
                  value={value}
                  checked={rules.pointsTo === value}
                  onChange={() => {
                    onChange({ ...rules, pointsTo: value });
                  }}
                  className="sr-only"
                />
                {value}
              </label>
            ))}
          </div>
        </fieldset>
        <label className="flex min-h-11 cursor-pointer items-center gap-3 text-body font-bold">
          <input
            type="checkbox"
            role="switch"
            checked={rules.winByTwo}
            onChange={(event) => {
              onChange({ ...rules, winByTwo: event.target.checked });
            }}
            className="relative h-[26px] w-11 cursor-pointer appearance-none rounded-full bg-line transition-colors duration-200 before:absolute before:top-[3px] before:left-[3px] before:size-5 before:rounded-full before:bg-surface before:shadow-sm before:transition-transform before:duration-200 before:ease-court checked:bg-primary checked:before:translate-x-[18px]"
          />
          Win by 2
        </label>
      </div>
      <p className="-mt-2 text-small text-muted">
        These are the starting choices when someone logs a game. They can change them each time.
      </p>
    </>
  );
}
