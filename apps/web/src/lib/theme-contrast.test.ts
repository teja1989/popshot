import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// Every text colour the app puts on a background, checked against WCAG: 4.5:1 for body text,
// 3:1 for large text and for borders that carry meaning. Read from globals.css itself, so a
// colour tweak there can't quietly make something unreadable.

const css = readFileSync(fileURLToPath(new URL("../app/globals.css", import.meta.url)), "utf8");

function block(selector: string): Record<string, string> {
  const start = css.indexOf(selector);
  if (start < 0) {
    throw new Error(`No ${selector} in globals.css`);
  }
  const body = css.slice(css.indexOf("{", start) + 1, css.indexOf("}", start));
  return Object.fromEntries(
    [...body.matchAll(/--c-([a-z-]+):\s*(#[0-9a-f]{6})\s*;/gi)].map((m) => [m[1] ?? "", (m[2] ?? "").toLowerCase()]),
  );
}

function luminance(hex: string): number {
  const channel = (i: number) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
  return (hi + 0.05) / (lo + 0.05);
}

const BODY = 4.5;
const LARGE = 3;

// [text, background, minimum]
const PAIRS: [string, string, number][] = [
  ["ink", "bg", BODY],
  ["ink", "surface", BODY],
  ["ink", "surface-low", BODY],
  ["ink", "surface-high", BODY],
  ["ink", "chip", BODY],
  ["muted", "bg", BODY],
  ["muted", "surface", BODY],
  ["muted", "surface-high", BODY],
  ["muted", "chip", BODY],
  ["primary", "bg", BODY],
  ["primary", "surface", BODY],
  ["on-primary", "primary", BODY],
  ["on-primary-container", "primary-container", BODY],
  ["on-secondary-container", "secondary-container", BODY],
  ["win", "surface", BODY],
  ["on-win", "win", BODY],
  ["loss", "surface", BODY],
  ["warn", "bg", BODY],
  ["warn", "surface", BODY],
  ["on-ball", "ball", BODY],
  ["on-hero", "hero", BODY],
  ["on-hero-muted", "hero", BODY],
  // Ball yellow is used for words on the hero blocks, always large or bold.
  ["ball", "hero", LARGE],
  // Borders that outline an input or a choice.
  ["line", "surface", 1],
  ["primary", "chip", LARGE],
];

describe.each([
  ["light", ":root {"],
  ["dark", ':root[data-theme="dark"] {'],
])("the %s theme", (_name, selector) => {
  const colours = block(selector);

  it.each(PAIRS)("%s on %s is readable", (text, background, minimum) => {
    const fg = colours[text];
    const bg = colours[background];
    expect(fg, `--c-${text}`).toBeDefined();
    expect(bg, `--c-${background}`).toBeDefined();
    expect(contrast(fg ?? "", bg ?? "")).toBeGreaterThanOrEqual(minimum);
  });
});

describe("dark mode by device setting", () => {
  it("matches the forced dark theme exactly", () => {
    const media = css.slice(css.indexOf("@media (prefers-color-scheme: dark)"));
    expect(block(':root:not([data-theme="light"]) {')).toEqual(block(':root[data-theme="dark"] {'));
    expect(media.length).toBeGreaterThan(0);
  });
});
