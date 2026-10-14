// The admin Learn pages. Shapes match the API's routes/admin_learn.py (migration 0029).

import type { Problem, Scene } from "./shot-scene";

export type Level = "beginner" | "intermediate" | "advanced" | "expert";

export interface ShotRow {
  id: string;
  slug: string;
  title: string;
  level: Level;
  focus_ids: string[];
  version: number;
  updated_at: string;
  updated_by: string | null;
  published_version: number | null;
  published_at: string | null;
}

export interface AdminShot extends ShotRow {
  summary: string;
  tips: string[];
  drill_steps: string[];
  // Null when it was saved under rules that have since changed.
  scene: Scene | null;
  slug_locked: boolean;
  problems: Problem[];
}

export const LEVEL_LABEL: Record<Level, string> = {
  beginner: "Beginner",
  intermediate: "Intermediate",
  advanced: "Advanced",
  expert: "Expert",
};

export type ShotState = "draft" | "published" | "changed";

/** Draft (never published or unpublished), published as is, or published with newer edits. */
export function shotState(shot: Pick<ShotRow, "version" | "published_version">): ShotState {
  if (shot.published_version === null) {
    return "draft";
  }
  return shot.published_version === shot.version ? "published" : "changed";
}

export const STATE_LABEL: Record<ShotState, string> = {
  draft: "Draft",
  published: "Published",
  changed: "Edits not published",
};
