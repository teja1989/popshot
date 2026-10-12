"use client";

import { useSyncExternalStore } from "react";

const noChange = () => () => undefined;

/** A date in the viewer's own time zone ("Sun, Oct 12"). Blank in the server render. */
export function LocalDate({ iso }: { iso: string }) {
  const text = useSyncExternalStore(
    noChange,
    () => new Date(iso).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" }),
    () => "",
  );
  return <time dateTime={iso}>{text}</time>;
}
