"use client";

import Link from "next/link";

import { myStatus, nightWhen, spotsLine, type Night } from "@/lib/nights";

import { RsvpButtons } from "./rsvp-buttons";
import { AvatarStack } from "./ui/avatar";

/** One play night: when, where, who's coming, and your answer. */
export function NightCard({
  night,
  showGroup = false,
  onChange,
}: {
  night: Night;
  showGroup?: boolean;
  onChange: (night: Night) => void;
}) {
  const status = myStatus(night);
  return (
    <article
      aria-label={`Meetup at ${night.venue}`}
      className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4"
    >
      <Link href={`/groups/${night.group_id}/nights/${night.id}`} className="flex flex-col gap-1 text-ink no-underline">
        <span className="flex items-baseline justify-between gap-3">
          <span className="text-[17px] font-extrabold">{nightWhen(night.starts_at)}</span>
          {night.cancelled && (
            <span className="shrink-0 rounded-full bg-chip px-2.5 py-0.5 text-[13px] font-bold text-warn">Cancelled</span>
          )}
        </span>
        <span className="truncate text-[15px] text-muted">
          {night.venue}
          {showGroup && ` · ${night.group_name}`}
        </span>
        <span className="mt-1 flex items-center gap-2 text-[14px] text-muted">
          {night.going.length > 0 && <AvatarStack people={night.going.slice(0, 4)} total={night.going.length} />}
          {spotsLine(night)}
        </span>
      </Link>
      {night.open && (
        <>
          {status && <p className="text-[14px] font-bold">{status}</p>}
          <RsvpButtons night={night} onChange={onChange} />
        </>
      )}
    </article>
  );
}
