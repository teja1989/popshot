import { describe, expect, it } from "vitest";

import { bodyOf, draftOf, draftReady, pickAction, pickForDay, type Pick } from "./library";

const ready = {
  ...draftOf(null),
  url: "https://youtu.be/dQw4w9WgXcQ",
  title: "Drops",
  source: "A Coach",
  skills: ["footwork"],
};

describe("a library draft", () => {
  it("is ready with a link, title, source and one to four skills", () => {
    expect(draftReady(ready)).toBe(true);
    expect(draftReady({ ...ready, url: "http://youtu.be/x" })).toBe(false);
    expect(draftReady({ ...ready, url: "javascript:alert(1)" })).toBe(false);
    expect(draftReady({ ...ready, title: "  " })).toBe(false);
    expect(draftReady({ ...ready, skills: [] })).toBe(false);
    expect(draftReady({ ...ready, skills: ["a", "b", "c", "d", "e"] })).toBe(false);
    expect(draftReady({ ...ready, minutes: "0" })).toBe(false);
    expect(draftReady({ ...ready, minutes: "121" })).toBe(false);
    expect(draftReady({ ...ready, minutes: "8" })).toBe(true);
  });

  it("goes to the API trimmed, with minutes as a number or none", () => {
    expect(bodyOf({ ...ready, title: " Drops ", minutes: "" }, "Because it's clear.")).toEqual({
      kind: "video",
      url: "https://youtu.be/dQw4w9WgXcQ",
      title: "Drops",
      source: "A Coach",
      skills: ["footwork"],
      levels: [],
      minutes: null,
      reason: "Because it's clear.",
    });
    expect(bodyOf({ ...ready, minutes: " 8 " }, "x").minutes).toBe(8);
  });
});

describe("picks", () => {
  const pick = (over: Partial<Pick>): Pick => ({
    id: "1",
    kind: "video",
    url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    title: "Drops",
    source: "A Coach",
    skills: ["footwork"],
    minutes: 8,
    ...over,
  });

  it("say what to do", () => {
    expect(pickAction(pick({}))).toBe("Watch · 8 min");
    expect(pickAction(pick({ kind: "article", minutes: null }))).toBe("Read");
  });

  it("give one a day, the same all day", () => {
    const picks = ["a", "b", "c"];
    const morning = pickForDay(picks, new Date(2026, 9, 12, 7));
    expect(pickForDay(picks, new Date(2026, 9, 12, 23))).toBe(morning);
    expect(pickForDay(picks, new Date(2026, 9, 13, 7))).not.toBe(morning);
    expect(pickForDay([], new Date())).toBeNull();
  });
});
