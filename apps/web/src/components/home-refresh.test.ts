import type { MouseEvent } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { homeTap, onHomeLinkClick } from "./home-refresh";

function click(over: Partial<MouseEvent<HTMLAnchorElement>> = {}) {
  const preventDefault = vi.fn();
  const event = {
    button: 0,
    metaKey: false,
    ctrlKey: false,
    shiftKey: false,
    altKey: false,
    preventDefault,
    ...over,
  } as unknown as MouseEvent<HTMLAnchorElement>;
  return { event, preventDefault };
}

function fakeWindow(scrollY: number, reducedMotion = false) {
  const win = {
    scrollY,
    scrollTo: vi.fn(),
    dispatchEvent: vi.fn(),
    matchMedia: vi.fn(() => ({ matches: reducedMotion })),
  };
  vi.stubGlobal("window", win);
  return win;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("homeTap", () => {
  it("scrolls when scrolled, refreshes at the top", () => {
    expect(homeTap(240)).toBe("scroll");
    expect(homeTap(0)).toBe("refresh");
  });
});

describe("onHomeLinkClick", () => {
  it("leaves the navigation alone away from Home", () => {
    const win = fakeWindow(0);
    const { event, preventDefault } = click();
    onHomeLinkClick("/games", event);
    expect(preventDefault).not.toHaveBeenCalled();
    expect(win.dispatchEvent).not.toHaveBeenCalled();
  });

  it.each([{ metaKey: true }, { ctrlKey: true }, { shiftKey: true }, { altKey: true }, { button: 1 }])(
    "leaves opening in a new tab or window to the browser (%o)",
    (over) => {
      const win = fakeWindow(0);
      const { event, preventDefault } = click(over);
      onHomeLinkClick("/", event);
      expect(preventDefault).not.toHaveBeenCalled();
      expect(win.dispatchEvent).not.toHaveBeenCalled();
    },
  );

  it("on Home, scrolled down: scrolls to the top, smoothly unless motion is reduced", () => {
    let win = fakeWindow(500);
    const { event, preventDefault } = click();
    onHomeLinkClick("/", event);
    expect(preventDefault).toHaveBeenCalled();
    expect(win.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: "smooth" });
    expect(win.dispatchEvent).not.toHaveBeenCalled();

    win = fakeWindow(500, true);
    onHomeLinkClick("/", click().event);
    expect(win.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: "auto" });
  });

  it("on Home, at the top: asks Home to refresh", () => {
    const win = fakeWindow(0);
    const { event, preventDefault } = click();
    onHomeLinkClick("/", event);
    expect(preventDefault).toHaveBeenCalled();
    expect(win.scrollTo).not.toHaveBeenCalled();
    expect(win.dispatchEvent).toHaveBeenCalledTimes(1);
    expect((win.dispatchEvent.mock.calls[0] as [Event])[0].type).toBe("popshot:home-refresh");
  });
});
