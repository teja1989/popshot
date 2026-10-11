import { describe, expect, it } from "vitest";

import { byArea, describeSuggestion, labelFor, MAX_IMPROVE, MAX_STRENGTHS, promote, toggle, wantsReflection } from "./focus";

const options = [
  { id: "serve_consistency", label: "Serve consistency", area: "Serve & return" },
  { id: "return_of_serve", label: "Return of serve", area: "Serve & return" },
  { id: "third_shot_drop", label: "Third-shot drops", area: "Third shot" },
];

describe("byArea", () => {
  it("groups in list order", () => {
    expect(byArea(options).map((g) => [g.area, g.options.length])).toEqual([
      ["Serve & return", 2],
      ["Third shot", 1],
    ]);
  });
});

describe("labelFor", () => {
  it("falls back to the ID for a retired option", () => {
    expect(labelFor(options, "third_shot_drop")).toBe("Third-shot drops");
    expect(labelFor(options, "old_thing")).toBe("old_thing");
  });
});

describe("describeSuggestion", () => {
  it("states what was observed", () => {
    expect(describeSuggestion({ option_id: "x", kind: "strength", count: 6, out_of: 10 }, "Third-shot drops")).toBe(
      "You picked Third-shot drops as going well in 6 of your last 10 games.",
    );
    expect(describeSuggestion({ option_id: "x", kind: "improve", count: 5, out_of: 5 }, "Footwork")).toBe(
      "You picked Footwork as something to improve in 5 of your last 5 games.",
    );
  });
});

describe("promote", () => {
  it("adds to the list and moves it out of the other", () => {
    expect(promote({ strengths: [], improve: ["footwork"] }, { option_id: "footwork", kind: "strength", count: 5, out_of: 5 })).toEqual({
      strengths: ["footwork"],
      improve: [],
    });
    expect(promote({ strengths: ["footwork"], improve: [] }, { option_id: "footwork", kind: "improve", count: 5, out_of: 5 })).toEqual({
      strengths: [],
      improve: ["footwork"],
    });
  });

  it("refuses when the list is full", () => {
    const full = { strengths: ["a", "b", "c", "d"].slice(0, MAX_STRENGTHS), improve: ["e", "f", "g"].slice(0, MAX_IMPROVE) };
    expect(promote(full, { option_id: "z", kind: "strength", count: 5, out_of: 5 })).toBeNull();
    expect(promote(full, { option_id: "z", kind: "improve", count: 5, out_of: 5 })).toBeNull();
  });
});

describe("toggle", () => {
  it("adds, removes and stops at the limit", () => {
    expect(toggle([], "a", 2)).toEqual(["a"]);
    expect(toggle(["a"], "a", 2)).toEqual([]);
    expect(toggle(["a", "b"], "c", 2)).toEqual(["a", "b"]);
  });
});

describe("wantsReflection", () => {
  const now = new Date("2026-10-11T12:00:00Z");
  const base = { i_played: true, my_reflection: null, played_at: "2026-10-10T12:00:00Z" };
  it.each([
    [base, true],
    [{ ...base, i_played: false }, false],
    [{ ...base, my_reflection: { went_well: [], to_improve: [] } }, false],
    [{ ...base, played_at: "2026-10-04T11:00:00Z" }, false],
  ])("%j -> %s", (match, expected) => {
    expect(wantsReflection(match, now)).toBe(expected);
  });
});
