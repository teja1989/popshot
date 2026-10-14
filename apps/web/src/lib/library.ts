// The content library (migration 0033): shapes from routes/admin_content.py and the
// journey picks, and small helpers for showing links.

export type Kind = "video" | "article";
export type Level = "beginner" | "intermediate" | "advanced" | "expert";
export type ItemStatus = "draft" | "published";

export const LEVELS: readonly Level[] = ["beginner", "intermediate", "advanced", "expert"];
export const LEVEL_LABEL: Record<Level, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
  expert: "Expert",
};
export const MAX_SKILLS = 4;

export interface LibraryItem {
  id: string;
  kind: Kind;
  url: string;
  title: string;
  source: string;
  skills: string[];
  levels: Level[];
  minutes: number | null;
  status: ItemStatus;
  updated_at: string;
  updated_by: string | null;
}

export interface LibraryHost {
  host: string;
  added_at: string;
}

export interface Pick {
  id: string;
  kind: Kind;
  url: string;
  title: string;
  source: string;
  skills: string[];
  minutes: number | null;
}

export interface ItemDraft {
  kind: Kind;
  url: string;
  title: string;
  source: string;
  skills: string[];
  levels: Level[];
  minutes: string;
}

export function draftOf(item: LibraryItem | null): ItemDraft {
  return {
    kind: item?.kind ?? "video",
    url: item?.url ?? "",
    title: item?.title ?? "",
    source: item?.source ?? "",
    skills: item ? [...item.skills] : [],
    levels: item ? [...item.levels] : [],
    minutes: item?.minutes ? String(item.minutes) : "",
  };
}

/** Whether the draft has what the API needs (it checks everything again). */
export function draftReady(draft: ItemDraft): boolean {
  const minutes = draft.minutes.trim();
  return (
    /^https:\/\/\S+$/.test(draft.url.trim()) &&
    draft.title.trim() !== "" &&
    draft.source.trim() !== "" &&
    draft.skills.length >= 1 &&
    draft.skills.length <= MAX_SKILLS &&
    (minutes === "" || (/^\d{1,3}$/.test(minutes) && Number(minutes) >= 1 && Number(minutes) <= 120))
  );
}

/** The body for the API, with the reason the admin gave. */
export function bodyOf(draft: ItemDraft, reason: string): Record<string, unknown> {
  const minutes = draft.minutes.trim();
  return {
    kind: draft.kind,
    url: draft.url.trim(),
    title: draft.title.trim(),
    source: draft.source.trim(),
    skills: draft.skills,
    levels: draft.levels,
    minutes: minutes === "" ? null : Number(minutes),
    reason,
  };
}

/** "Watch · 8 min" or "Read", for a pick's button. */
export function pickAction(pick: Pick): string {
  const verb = pick.kind === "video" ? "Watch" : "Read";
  return pick.minutes ? `${verb} · ${String(pick.minutes)} min` : verb;
}

/** One pick for the day, moving on each day, from the closest matches. */
export function pickForDay<T>(picks: readonly T[], date: Date): T | null {
  if (picks.length === 0) {
    return null;
  }
  const day = Math.floor(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()) / 86_400_000);
  return picks[day % picks.length] ?? null;
}
