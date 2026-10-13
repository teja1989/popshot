import { describe, expect, it } from "vitest";

import { featureOn } from "./features";

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
