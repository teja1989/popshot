"use client";

import type { GroupSummary } from "@/lib/groups";

export function GroupSwitcher({
  groups,
  current,
  onChange,
}: {
  groups: GroupSummary[];
  current: GroupSummary;
  onChange: (groupId: string) => void;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-bold tracking-[0.1em] text-muted uppercase">Group</span>
      <span className="relative">
        <select
          value={current.id}
          onChange={(event) => {
            onChange(event.target.value);
          }}
          className="min-h-12 w-full max-w-sm cursor-pointer appearance-none rounded-xl border border-line bg-surface py-2 pr-10 pl-4 text-[18px] font-bold text-ink"
        >
          {groups.map((group) => (
            <option key={group.id} value={group.id}>
              {group.name}
            </option>
          ))}
        </select>
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          aria-hidden="true"
          className="pointer-events-none absolute top-1/2 left-[min(calc(100%-28px),calc(24rem-28px))] -translate-y-1/2 text-muted"
        >
          <path d="M4 6l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
    </label>
  );
}
