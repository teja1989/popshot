"use client";

import { useCallback, useState } from "react";

import type { GroupSummary } from "@/lib/groups";

// The group Games and Board show. Remembered on this device only; falls back to your first
// group when nothing is saved or the saved one is gone.

const KEY = "popshot.group";

function readSaved(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

/** Make `groupId` the group Games and Board open on (say, after logging a game there). */
export function rememberGroup(groupId: string): void {
  try {
    localStorage.setItem(KEY, groupId);
  } catch {
    // Storage blocked: Games falls back to your first group.
  }
}

export function useCurrentGroup(groups: GroupSummary[]): {
  current: GroupSummary | null;
  choose: (groupId: string) => void;
} {
  // Rendered in the browser only (inside the app shell), so storage can be read up front.
  const [saved, setSaved] = useState<string | null>(readSaved);

  const choose = useCallback((groupId: string) => {
    setSaved(groupId);
    rememberGroup(groupId);
  }, []);

  const current = groups.find((g) => g.id === saved) ?? groups[0] ?? null;
  return { current, choose };
}
