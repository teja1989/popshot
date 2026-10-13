import { describe, expect, it } from "vitest";

import { areasOf, filterFeatures, planState, reachText, type Feature } from "./admin-features";

function feature(over: Partial<Feature>): Feature {
  return {
    key: "events.shuffle",
    area: "events",
    title: "Shuffle",
    description: "Round robin with rotating partners.",
    needs_plan: null,
    rollout: "off",
    crews: 0,
    updated_at: "2026-10-13T12:00:00Z",
    updated_by: null,
    ...over,
  };
}

const ALL = [
  feature({}),
  feature({
    key: "events.river",
    title: "River",
    description: "Up and down the river.",
    needs_plan: "organizer",
    rollout: "crews",
    crews: 2,
  }),
  feature({
    key: "recaps.ai",
    area: "recaps",
    title: "AI recap writing",
    description: "AI words.",
    rollout: "everyone",
  }),
  feature({ key: "beta.thing", area: "zeta", title: "Something new", description: "New." }),
];

describe("admin features", () => {
  it("lists the areas that have features, in menu order, unknown ones last", () => {
    expect(areasOf(ALL)).toEqual(["events", "recaps", "zeta"]);
    expect(areasOf([])).toEqual([]);
  });

  it("filters by area, rollout and search", () => {
    const keys = (fs: Feature[]) => fs.map((f) => f.key);
    expect(keys(filterFeatures(ALL, { area: "events", query: "", rollout: null }))).toEqual([
      "events.shuffle",
      "events.river",
    ]);
    expect(keys(filterFeatures(ALL, { area: null, query: "", rollout: "everyone" }))).toEqual(["recaps.ai"]);
    expect(keys(filterFeatures(ALL, { area: null, query: "  RIVER ", rollout: null }))).toEqual(["events.river"]);
    expect(keys(filterFeatures(ALL, { area: null, query: "rotating", rollout: null }))).toEqual(["events.shuffle"]);
    expect(filterFeatures(ALL, { area: "recaps", query: "", rollout: "off" })).toEqual([]);
  });

  it("says who has it", () => {
    expect(reachText({ rollout: "off", needs_plan: "organizer", crews: 3 })).toBe("Off for everyone");
    expect(reachText({ rollout: "crews", needs_plan: null, crews: 1 })).toBe("1 selected crew");
    expect(reachText({ rollout: "crews", needs_plan: null, crews: 3 })).toBe("3 selected crews");
    expect(reachText({ rollout: "everyone", needs_plan: null, crews: 0 })).toBe("Every crew");
    expect(reachText({ rollout: "everyone", needs_plan: "organizer", crews: 0 })).toBe("Every crew on Organizer");
  });

  it("knows whether a plan is running", () => {
    const now = new Date("2026-10-13T12:00:00Z");
    expect(planState({ starts_at: "2026-10-01T00:00:00Z", ends_at: null }, now)).toBe("running");
    expect(planState({ starts_at: "2026-10-01T00:00:00Z", ends_at: "2026-11-01T00:00:00Z" }, now)).toBe("running");
    expect(planState({ starts_at: "2026-10-01T00:00:00Z", ends_at: "2026-10-13T12:00:00Z" }, now)).toBe("ended");
    expect(planState({ starts_at: "2026-10-14T00:00:00Z", ends_at: null }, now)).toBe("not_started");
  });
});
