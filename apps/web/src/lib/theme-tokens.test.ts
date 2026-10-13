import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

// Tailwind makes text-<name> from both --color-<name> and --text-<name>. If a color and a
// type size share a name, text-<name> sets the color too: a "hero"-sized headline once came
// out in the hero's own blue, invisible on it.
const css = readFileSync(join(__dirname, "..", "app", "globals.css"), "utf8");

function names(prefix: string): string[] {
  const pattern = new RegExp(`--${prefix}-([a-z][a-z0-9-]*?)(?:--[a-z-]+)?:`, "g");
  return [...new Set([...css.matchAll(pattern)].map((match) => match[1] ?? ""))].filter((name) => name !== "");
}

describe("theme tokens", () => {
  it("has type sizes and colors", () => {
    expect(names("text")).toContain("body");
    expect(names("color")).toContain("ink");
  });

  it("never gives a type size the same name as a color", () => {
    const colors = new Set(names("color"));
    expect(names("text").filter((name) => colors.has(name))).toEqual([]);
  });
});
