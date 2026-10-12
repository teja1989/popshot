// What a crew's settings page shows, and to whom. The page is a list of sections; each
// one says who sees it. Adding a feature's settings is one entry here and one component in
// crew-settings-view.tsx (TypeScript insists on both).

import type { GroupDetail } from "./groups";

/** A crew's plan. Everyone is on "free" until subscriptions exist; planOf is the one place
 *  that will read the real plan (from the crew, once the API sends it), and sections can
 *  then depend on it through SettingsContext. */
export type Plan = "free";

export function planOf(): Plan {
  return "free";
}

export interface SettingsContext {
  role: GroupDetail["my_role"];
  status: GroupDetail["my_status"];
  plan: Plan;
}

export type SectionId = "crew" | "rules" | "leave";

interface Section {
  id: SectionId;
  show: (ctx: SettingsContext) => boolean;
}

const runsTheCrew = (ctx: SettingsContext) =>
  ctx.status === "active" && (ctx.role === "lead" || ctx.role === "co_lead");

/** In page order. */
export const SECTIONS: readonly Section[] = [
  { id: "crew", show: runsTheCrew },
  { id: "rules", show: runsTheCrew },
  // Leave (or cancel a request to join) for everyone; the lead sees Delete here instead.
  { id: "leave", show: () => true },
];

export function sectionsFor(group: GroupDetail): SectionId[] {
  const ctx: SettingsContext = { role: group.my_role, status: group.my_status, plan: planOf() };
  return SECTIONS.filter((s) => s.show(ctx)).map((s) => s.id);
}
