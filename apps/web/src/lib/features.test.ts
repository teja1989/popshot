import { describe, expect, it } from "vitest";

import { featureOn, youOn } from "./features";

describe("feature switches", () => {
  const mine = { crews: { a: ["events.shuffle", "recaps.ai"], b: ["recaps.ai"] }, everywhere: [] };

  it("answers per crew", () => {
    expect(featureOn(mine, "events.shuffle", "a")).toBe(true);
    expect(featureOn(mine, "events.shuffle", "b")).toBe(false);
    expect(featureOn(mine, "events.shuffle", "not-mine")).toBe(false);
    expect(featureOn(mine, "events.shuffle", null)).toBe(false);
  });

  it("matches a whole area with .*", () => {
    expect(featureOn(mine, "events.*", "a")).toBe(true);
    expect(featureOn(mine, "events.*", "b")).toBe(false);
    // "events.*" is not "eventsfoo".
    expect(featureOn({ crews: { a: ["eventsx.thing"] }, everywhere: [] }, "events.*", "a")).toBe(false);
  });
});

describe("per-person switches", () => {
  it("answers for you, whatever crew is picked", () => {
    const mine = { crews: {}, everywhere: [], you: ["you.journey"] };
    expect(youOn(mine, "you.journey")).toBe(true);
    expect(youOn(mine, "you.journey_ai")).toBe(false);
    expect(youOn(mine, "you.*")).toBe(true);
    expect(youOn(mine, "events.*")).toBe(false);
  });

  it("is off when an older answer has no list", () => {
    expect(youOn({ crews: { a: ["you.journey"] }, everywhere: ["you.journey"] }, "you.journey")).toBe(false);
  });
});
