import { describe, expect, it } from "vitest";

import { courtMapsUrl, initialWhere, inOrder, wherePayload, type Court } from "./courts";

const court = (id: string, label: string, isDefault = false, google: string | null = null): Court => ({
  id,
  label,
  google_place_id: google,
  is_default: isDefault,
});

const riverside = court("a", "Riverside", false, "ChIJ1");
const hall = court("b", "Hall", true);

describe("inOrder", () => {
  it("puts the default first and keeps the rest in order", () => {
    expect(inOrder([riverside, court("c", "Park"), hall]).map((c) => c.label)).toEqual(["Hall", "Riverside", "Park"]);
  });
});

describe("courtMapsUrl", () => {
  it("links Google courts only", () => {
    expect(courtMapsUrl(riverside)).toContain("query_place_id=ChIJ1");
    expect(courtMapsUrl(hall)).toBeNull();
  });
});

describe("initialWhere", () => {
  it("starts a new meetup at the default court", () => {
    expect(initialWhere([riverside, hall], undefined, "Old place")).toEqual({ kind: "court", court: hall });
  });

  it("falls back to where the crew played last", () => {
    expect(initialWhere([], undefined, "Old place")).toEqual({ kind: "elsewhere", venue: "Old place" });
    expect(initialWhere([court("x", "X")], undefined, undefined)).toEqual({ kind: "elsewhere", venue: "" });
  });

  it("keeps a meetup's court, or its own venue when the court is gone", () => {
    expect(initialWhere([riverside, hall], { venue: "Riverside", court_id: "a" }, undefined)).toEqual({
      kind: "court",
      court: riverside,
    });
    expect(initialWhere([hall], { venue: "Riverside", court_id: "a" }, undefined)).toEqual({
      kind: "elsewhere",
      venue: "Riverside",
    });
  });
});

describe("wherePayload", () => {
  it("names the court, or sends the typed venue without one", () => {
    expect(wherePayload({ kind: "court", court: hall })).toEqual({ venue: "Hall", court_id: "b" });
    expect(wherePayload({ kind: "elsewhere", venue: "  Beach " })).toEqual({ venue: "Beach", court_id: null });
  });
});
