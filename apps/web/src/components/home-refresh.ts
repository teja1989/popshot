"use client";

import { useEffect, type MouseEvent } from "react";

// Tapping the logo or the Home tab while already on Home: scroll back to the top, or, at the
// top, fetch Home's data again. Home's sections listen for the refresh.

const REFRESH = "popshot:home-refresh";

/** What a tap on a link home does when you're already home. */
export function homeTap(scrollY: number): "scroll" | "refresh" {
  return scrollY > 0 ? "scroll" : "refresh";
}

/** For links to Home: on Home, scroll up or refresh instead of a navigation that does nothing. */
export function onHomeLinkClick(pathname: string, event: MouseEvent<HTMLAnchorElement>): void {
  // Opening in a new tab or window is left to the browser.
  if (pathname !== "/" || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
    return;
  }
  event.preventDefault();
  if (homeTap(window.scrollY) === "scroll") {
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: still ? "auto" : "smooth" });
  } else {
    window.dispatchEvent(new Event(REFRESH));
  }
}

/** Calls `onRefresh` when Home is asked to refresh. Pass a stable function. */
export function useHomeRefresh(onRefresh: () => void): void {
  useEffect(() => {
    window.addEventListener(REFRESH, onRefresh);
    return () => {
      window.removeEventListener(REFRESH, onRefresh);
    };
  }, [onRefresh]);
}
