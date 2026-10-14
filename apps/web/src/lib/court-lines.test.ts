import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { BANNED } from "./copy-rules";
import { COURT_LINES, pickLine } from "./court-lines";

describe("court lines", () => {
  it.each(COURT_LINES)("are short and kind: %s", (line) => {
    expect(line.length).toBeLessThanOrEqual(60);
    expect(line).not.toMatch(BANNED);
  });

  it("are all different, and include one last game", () => {
    expect(new Set(COURT_LINES).size).toBe(COURT_LINES.length);
    expect(COURT_LINES.some((line) => line.startsWith("One last game"))).toBe(true);
  });

  it("never shows the same line twice in a row", () => {
    for (const previous of COURT_LINES) {
      for (const r of [0, 0.5, 0.999999]) {
        expect(pickLine(previous, () => r)).not.toBe(previous);
      }
    }
  });

  it("can show any line, and copes with no previous one or an unknown one", () => {
    const seen = new Set<string>();
    for (let i = 0; i < COURT_LINES.length; i++) {
      seen.add(pickLine(null, () => i / COURT_LINES.length));
    }
    expect(seen.size).toBe(COURT_LINES.length);
    expect(COURT_LINES).toContain(pickLine("not a line", () => 0.3));
  });
});

// "AI" only appears in notes (the privacy page) and admin; everywhere else Popshot just
// names what it uses (Google Gemini).
const SRC = join(__dirname, "..");
const ALLOWED = [/[/\\]app[/\\]privacy[/\\]/, /[/\\]admin/, /\.test\.ts$/];

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sourceFiles(path);
    return /\.tsx?$/.test(name) ? [path] : [];
  });
}

function aiInCopy(source: string): string[] {
  return source
    .split("\n")
    .filter((line) => !/^\s*(\/\/|\*|\/\*)/.test(line))
    .filter((line) => /\bAI\b/.test(line));
}

describe("app copy", () => {
  it("doesn't say AI outside the notes", () => {
    const found = sourceFiles(SRC)
      .filter((path) => !ALLOWED.some((rule) => rule.test(path)))
      .flatMap((path) => aiInCopy(readFileSync(path, "utf8")).map((line) => `${path}: ${line.trim()}`));
    expect(found).toEqual([]);
  });

  it("catches AI in copy, not in comments", () => {
    expect(aiInCopy("  <p>Written by AI.</p>\n  // the AI writer")).toHaveLength(1);
    expect(aiInCopy("  // Gemini (AI)\n   * AI note")).toHaveLength(0);
  });
});
