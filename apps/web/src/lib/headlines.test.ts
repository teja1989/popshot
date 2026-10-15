import { describe, expect, it } from "vitest";

import { BANNED } from "./copy-rules";
import { FIRST, HEADLINES, headlineOrder, headlineText } from "./headlines";

describe("landing headlines", () => {
  it.each(HEADLINES.map(headlineText))("are short and kind: %s", (text) => {
    // The jumbo type fits about 30 characters in two lines on a phone.
    expect(text.length).toBeLessThanOrEqual(30);
    expect(text).not.toMatch(BANNED);
    expect(text).not.toMatch(/\bAI\b/);
  });

  it("are all different, and start with one last game", () => {
    const texts = HEADLINES.map(headlineText);
    expect(new Set(texts).size).toBe(texts.length);
    expect(HEADLINES[0]).toBe(FIRST);
    expect(headlineText(FIRST)).toBe("One last game.");
  });

  it("keep their promises small: no health claims", () => {
    for (const text of HEADLINES.map(headlineText)) {
      expect(text).not.toMatch(/\b(cure|prevent|lose weight|burn|calorie|guarantee|doctor)/i);
    }
  });
});

describe("headlineOrder", () => {
  it("always opens with one last game, and shows every line once", () => {
    for (const r of [0, 0.37, 0.999]) {
      const order = headlineOrder(() => r);
      expect(order[0]).toBe(FIRST);
      expect(new Set(order.map(headlineText))).toEqual(new Set(HEADLINES.map(headlineText)));
      expect(order).toHaveLength(HEADLINES.length);
    }
  });

  it("shuffles the rest", () => {
    let seed = 1;
    const random = () => {
      seed = (seed * 16807) % 2147483647;
      return seed / 2147483647;
    };
    const a = headlineOrder(random).map(headlineText);
    const b = headlineOrder(random).map(headlineText);
    expect(a).not.toEqual(HEADLINES.map(headlineText));
    expect(a).not.toEqual(b);
  });
});
