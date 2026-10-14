"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

// How long to wait for a page's content to load before giving up on the #section.
const WAIT_MS = 5000;

/**
 * Links like /you#focus-heading point at a section that only appears once the page has loaded
 * its data, too late for the browser's own jump. This waits for it, scrolls to it and moves
 * focus there, so keyboard and screen reader users land in the same place.
 */
export function HashScroll() {
  const pathname = usePathname();

  useEffect(() => {
    const id = decodeURIComponent(window.location.hash.slice(1));
    if (!id) {
      return;
    }
    function land(): boolean {
      const target = document.getElementById(id);
      if (!target) {
        return false;
      }
      if (!target.hasAttribute("tabindex")) {
        target.setAttribute("tabindex", "-1");
      }
      target.scrollIntoView({ block: "start" });
      target.focus({ preventScroll: true });
      return true;
    }
    if (land()) {
      return;
    }
    const watcher = new MutationObserver(() => {
      if (land()) {
        stop();
      }
    });
    const timer = window.setTimeout(stop, WAIT_MS);
    function stop() {
      watcher.disconnect();
      window.clearTimeout(timer);
    }
    watcher.observe(document.body, { childList: true, subtree: true });
    return stop;
  }, [pathname]);

  return null;
}
