import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { CATEGORY_LABEL, isIos, keyBytes, knownCategories } from "./push";

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

describe("notification categories", () => {
  it("leaves out a category it has no label for, instead of crashing", () => {
    expect(knownCategories(["invites", "something_new", "games"])).toEqual(["invites", "games"]);
    expect(knownCategories(["constructor", "toString"])).toEqual([]);
  });

  it("has a label for every category the API offers", () => {
    // The API's list (routes/notifications.py OFFERED). A category added there needs a
    // label here, or people never see its switch.
    const source = readFileSync(
      fileURLToPath(new URL("../../../../services/api/src/popshot_api/routes/notifications.py", import.meta.url)),
      "utf8",
    );
    const offered = /OFFERED: tuple\[Category, \.\.\.\] = \(([^)]*)\)/.exec(source)?.[1];
    expect(offered).toBeTruthy();
    const names = [...(offered ?? "").matchAll(/"([a-z_]+)"/g)].map((m) => m[1] ?? "");
    expect(names.length).toBeGreaterThan(0);
    for (const name of names) {
      expect(Object.hasOwn(CATEGORY_LABEL, name), name).toBe(true);
    }
  });
});
