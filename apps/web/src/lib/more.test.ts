import { describe, expect, it } from "vitest";

import { availableItems, isNew, MORE_ITEMS, NEW_DAYS, searchItems, SECTIONS, type MoreItem } from "./more";

const ids = (items: readonly MoreItem[]) => items.map((item) => item.id);
const nothingOn = () => false;

describe("the More list", () => {
  it("has unique ids, a known section, and either a page or an action for every item", () => {
    expect(new Set(ids(MORE_ITEMS)).size).toBe(MORE_ITEMS.length);
    for (const item of MORE_ITEMS) {
      expect(SECTIONS).toContain(item.section);
      expect(Boolean(item.href) !== Boolean(item.action)).toBe(true);
    }
  });

  it("opens crew pages for the picked crew", () => {
    const log = MORE_ITEMS.find((item) => item.id === "log");
    expect(log?.href?.("abc")).toBe("/groups/abc/log");
    const members = MORE_ITEMS.find((item) => item.id === "members");
    expect(members?.href?.("abc")).toBe("/groups/abc/members");
  });

  it("leaves out crew items when you have no crew", () => {
    const shown = ids(availableItems(MORE_ITEMS, { crewId: null, featureOn: () => true }));
    expect(shown).not.toContain("log");
    expect(shown).not.toContain("members");
    expect(shown).toEqual(expect.arrayContaining(["stats", "start", "join", "help", "sign-out"]));
  });

  it("shows switched features only while they're on for the picked crew", () => {
    const off = ids(availableItems(MORE_ITEMS, { crewId: "abc", featureOn: nothingOn }));
    expect(off).not.toContain("events");
    const on = ids(availableItems(MORE_ITEMS, { crewId: "abc", featureOn: (key) => key === "events.*" }));
    expect(on).toContain("events");
  });

  it("shows per-person switches only while they're on for you, crew or not", () => {
    expect(ids(availableItems(MORE_ITEMS, { crewId: null, featureOn: () => true }))).not.toContain("journey");
    const on = { crewId: null, featureOn: nothingOn, youOn: (key: string) => key === "you.journey" };
    expect(ids(availableItems(MORE_ITEMS, on))).toContain("journey");
  });

  it("never links a crew page without a crew", () => {
    for (const item of availableItems(MORE_ITEMS, { crewId: null, featureOn: () => true })) {
      expect(item.href?.(null) ?? "").not.toContain("/groups/");
    }
  });
});

describe("search", () => {
  it("matches labels, descriptions and keywords, ignoring case and accents", () => {
    expect(ids(searchItems(MORE_ITEMS, "INVITE"))).toEqual(expect.arrayContaining(["members", "join", "code"]));
    expect(ids(searchItems(MORE_ITEMS, "round robin"))).toEqual(["events"]);
    expect(ids(searchItems(MORE_ITEMS, "rsvp"))).toEqual(["meetups"]);
    expect(ids(searchItems(MORE_ITEMS, "délete"))).toContain("data");
  });

  it("needs every word to match, and shows everything when empty", () => {
    expect(ids(searchItems(MORE_ITEMS, "invite xylophone"))).toEqual([]);
    expect(searchItems(MORE_ITEMS, "   ")).toHaveLength(MORE_ITEMS.length);
  });
});

describe("new items", () => {
  const item = { id: "x", section: "play", label: "X", description: "X", added: "2026-10-13" } as const;

  it("are new for two weeks from the day they arrive", () => {
    expect(NEW_DAYS).toBe(14);
    expect(isNew(item, "2026-10-12")).toBe(false);
    expect(isNew(item, "2026-10-13")).toBe(true);
    expect(isNew(item, "2026-10-26")).toBe(true);
    expect(isNew(item, "2026-10-27")).toBe(false);
    expect(isNew({ ...item, added: undefined }, "2026-10-13")).toBe(false);
  });
});
