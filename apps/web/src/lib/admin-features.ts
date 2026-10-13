// The admin Features page: feature switches and crew plans. Shapes match the API's
// routes/admin_features.py (migration 0027).

export type Rollout = "off" | "crews" | "everyone";
export type Plan = "organizer";
export type PlanSource = "beta" | "comp" | "subscription";

export interface Feature {
  key: string;
  area: string;
  title: string;
  description: string;
  needs_plan: Plan | null;
  rollout: Rollout;
  crews: number;
  updated_at: string;
  updated_by: string | null;
}

export interface FeatureCrew {
  group_id: string;
  name: string;
  added_at: string;
  added_by: string | null;
}

export interface CrewPlan {
  plan: Plan;
  source: PlanSource;
  starts_at: string;
  ends_at: string | null;
  note: string | null;
  granted_at: string;
  granted_by: string | null;
}

export interface CrewAccess {
  plans: CrewPlan[];
  features: string[];
}

export interface PlanRow {
  group_id: string;
  name: string;
  plan: Plan;
  source: PlanSource;
  starts_at: string;
  ends_at: string | null;
  note: string | null;
}

// The order the tabs appear in. Only areas that have a feature get a tab.
export const AREAS = ["events", "learn", "play", "crew", "recaps", "courts", "home", "you"] as const;

export const AREA_LABEL: Record<string, string> = {
  events: "Events",
  learn: "Learn",
  play: "Play",
  crew: "Crew",
  recaps: "Recaps",
  courts: "Courts",
  home: "Home",
  you: "You",
};

export const ROLLOUTS: readonly Rollout[] = ["off", "crews", "everyone"];

export const ROLLOUT_LABEL: Record<Rollout, string> = {
  off: "Off",
  crews: "Selected crews",
  everyone: "Everyone",
};

export const SOURCE_LABEL: Record<PlanSource, string> = {
  beta: "Beta",
  comp: "Complimentary",
  subscription: "Subscription",
};

/** The areas that have at least one feature, in AREAS order (unknown areas last). */
export function areasOf(features: readonly Feature[]): string[] {
  const present = new Set(features.map((f) => f.area));
  const known = AREAS.filter((a) => present.has(a));
  const unknown = [...present].filter((a) => !(AREAS as readonly string[]).includes(a)).sort();
  return [...known, ...unknown];
}

export interface FeatureFilter {
  area: string | null;
  query: string;
  rollout: Rollout | null;
}

export function filterFeatures(features: readonly Feature[], filter: FeatureFilter): Feature[] {
  const query = filter.query.trim().toLowerCase();
  return features.filter(
    (f) =>
      (filter.area === null || f.area === filter.area) &&
      (filter.rollout === null || f.rollout === filter.rollout) &&
      (query === "" ||
        f.title.toLowerCase().includes(query) ||
        f.key.toLowerCase().includes(query) ||
        f.description.toLowerCase().includes(query)),
  );
}

/** Who has it, in a few words: "Off for everyone", "3 selected crews", "Everyone on Organizer". */
export function reachText(feature: Pick<Feature, "rollout" | "needs_plan" | "crews">): string {
  if (feature.rollout === "off") {
    return "Off for everyone";
  }
  if (feature.rollout === "crews") {
    return feature.crews === 1 ? "1 selected crew" : `${String(feature.crews)} selected crews`;
  }
  return feature.needs_plan ? "Every crew on Organizer" : "Every crew";
}

export type PlanState = "running" | "ended" | "not_started";

export function planState(plan: Pick<CrewPlan, "starts_at" | "ends_at">, now: Date): PlanState {
  if (new Date(plan.starts_at) > now) {
    return "not_started";
  }
  if (plan.ends_at !== null && new Date(plan.ends_at) <= now) {
    return "ended";
  }
  return "running";
}
