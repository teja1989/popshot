import { describe, expect, it } from "vitest";

import { isIos, keyBytes } from "./push";

describe("push helpers", () => {
  it("decodes a base64url key", () => {
    // 0xfb 0xff 0xbf uses both URL-safe characters.
    expect(Array.from(keyBytes("-_-_"))).toEqual([0xfb, 0xff, 0xbf]);
    expect(Array.from(keyBytes("AQ"))).toEqual([1]);
    expect(keyBytes("BAAA").length).toBe(3);
  });

  it.each([
    ["Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)", 5, true],
    ["Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", 5, true], // iPad
    ["Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", 0, false], // a Mac
    ["Mozilla/5.0 (Linux; Android 15; Pixel 9)", 5, false],
  ])("isIos(%s, %d)", (ua, touch, expected) => {
    expect(isIos(ua, touch)).toBe(expected);
  });
});
