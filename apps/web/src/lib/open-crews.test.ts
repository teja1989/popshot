import { describe, expect, it } from "vitest";

import { distanceLabel, loadStart, locationProblem, placeProblem, saveStart, spaceLabel } from "./open-crews";

function memory() {
  const items = new Map<string, string>();
  return {
    items,
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => {
      items.set(key, value);
    },
    removeItem: (key: string) => {
      items.delete(key);
    },
  };
}

describe("the remembered start", () => {
  it("round-trips a place and your location", () => {
    const store = memory();
    saveStart(store, { kind: "place", placeId: "fake-riverside-park", label: "Riverside Park" });
    expect(loadStart(store)).toEqual({ kind: "place", placeId: "fake-riverside-park", label: "Riverside Park" });
    saveStart(store, { kind: "here" });
    expect(loadStart(store)).toEqual({ kind: "here" });
    saveStart(store, null);
    expect(loadStart(store)).toBeNull();
  });

  it("never keeps coordinates", () => {
    const store = memory();
    saveStart(store, { kind: "here" });
    expect([...store.items.values()].join()).not.toMatch(/\d+\.\d+/);
  });

  it("ignores anything it didn't write", () => {
    const store = memory();
    for (const raw of [
      "not json",
      "null",
      '"here"',
      '{"kind":"place","placeId":"bad id!","label":"x"}',
      '{"kind":"place","placeId":"ok","label":""}',
      '{"kind":"elsewhere"}',
    ]) {
      store.items.set("popshot.find.start", raw);
      expect(loadStart(store)).toBeNull();
    }
  });

  it("copes when storage throws or isn't there", () => {
    const broken = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
      removeItem: () => {
        throw new Error("blocked");
      },
    };
    expect(loadStart(broken)).toBeNull();
    expect(() => {
      saveStart(broken, { kind: "here" });
    }).not.toThrow();
    expect(loadStart(null)).toBeNull();
  });
});

describe("labels", () => {
  it("rounds distances sensibly", () => {
    expect(distanceLabel(0.4)).toBe("Under 1 km");
    expect(distanceLabel(3.44)).toBe("3.4 km");
    expect(distanceLabel(18.6)).toBe("19 km");
  });

  it("says how much space a crew has", () => {
    expect(spaceLabel({ members: 7, max_members: 12, full: false })).toBe("7 of 12 players");
    expect(spaceLabel({ members: 11, max_members: 12, full: false })).toBe("1 spot left");
    expect(spaceLabel({ members: 12, max_members: 12, full: true })).toBe("Full");
    expect(spaceLabel({ members: 14, max_members: 12, full: false })).toBe("Full");
  });

  it("explains location and place problems", () => {
    expect(locationProblem(1)).toContain("Location is off");
    expect(locationProblem(3)).toContain("couldn't get your location");
    expect(placeProblem("found")).toBeNull();
    expect(placeProblem("not_found")).toContain("can't find");
    expect(placeProblem("unavailable")).toContain("isn't working");
  });
});
