import { describe, expect, it } from "vitest";

import { CLOSE_DISTANCE, CLOSE_SPEED, closesOnRelease } from "./sheet-drag";

describe("closing a sheet by dragging it down", () => {
  it("closes past the distance, or on a quick flick", () => {
    expect(closesOnRelease(CLOSE_DISTANCE + 1, 0)).toBe(true);
    expect(closesOnRelease(20, CLOSE_SPEED + 1)).toBe(true);
  });

  it("springs back after a short, slow drag, or a drag upwards", () => {
    expect(closesOnRelease(CLOSE_DISTANCE, 0)).toBe(false);
    expect(closesOnRelease(40, 100)).toBe(false);
    expect(closesOnRelease(-200, -900)).toBe(false);
  });
});
