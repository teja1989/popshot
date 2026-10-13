"use client";

import { useState } from "react";

import { initials, usablePhoto } from "@/lib/people";

// A profile photo when there is one, initials otherwise (and if the photo fails to load).

const TONES = { chip: "bg-chip text-ink", ball: "bg-ball text-on-ball" };
const SIZES = {
  sm: "size-8 text-label",
  md: "size-10 text-meta",
  lg: "size-14 text-lead",
};

export function Avatar({
  name,
  photoUrl,
  tone = "chip",
  size = "md",
  className = "",
}: {
  name: string | null | undefined;
  photoUrl?: string | null;
  tone?: keyof typeof TONES;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const photo = failed ? null : usablePhoto(photoUrl);
  const frame = `flex shrink-0 items-center justify-center overflow-hidden rounded-full font-extrabold uppercase ${SIZES[size]} ${className}`;
  if (photo) {
    return (
      // A plain <img>: next/image would proxy Google's photos through our server.
      <img
        src={photo}
        alt=""
        aria-hidden="true"
        referrerPolicy="no-referrer"
        loading="lazy"
        decoding="async"
        className={`${frame} bg-chip object-cover`}
        onError={() => {
          setFailed(true);
        }}
      />
    );
  }
  return (
    <span aria-hidden="true" className={`${frame} ${TONES[tone]}`}>
      {initials(name)}
    </span>
  );
}

/** Overlapping faces for a group card, with "+N" when there are more. */
export function AvatarStack({
  people,
  total,
}: {
  people: { display_name: string; avatar_url: string | null }[];
  total: number;
}) {
  const extra = total - people.length;
  return (
    <span aria-hidden="true" className="flex items-center">
      {people.map((person, index) => (
        <Avatar
          key={`${person.display_name}-${String(index)}`}
          name={person.display_name}
          photoUrl={person.avatar_url}
          tone={index === 0 ? "ball" : "chip"}
          size="sm"
          className={`ring-2 ring-surface ${index > 0 ? "-ml-1" : ""}`}
        />
      ))}
      {extra > 0 && (
        <span className="-ml-1 flex size-8 items-center justify-center rounded-full bg-chip text-label font-extrabold text-muted ring-2 ring-surface">
          +{extra}
        </span>
      )}
    </span>
  );
}
