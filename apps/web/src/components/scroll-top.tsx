"use client";

import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";

/**
 * A tap to another page starts at its top. Next.js does that itself between most pages, but
 * not between two pages under the same parent (You → Settings → You kept the old scroll). Back
 * and forward keep the browser's own scroll memory, and a #section link is left to HashScroll.
 */
export function ScrollTop() {
  const pathname = usePathname();
  const first = useRef(true);
  const popped = useRef(false);

  useEffect(() => {
    const onPop = () => {
      popped.current = true;
    };
    window.addEventListener("popstate", onPop);
    return () => {
      window.removeEventListener("popstate", onPop);
    };
  }, []);

  useEffect(() => {
    // Not on the first page you open (a reload keeps its place), nor after back or forward.
    if (first.current || popped.current) {
      first.current = false;
      popped.current = false;
      return;
    }
    if (!window.location.hash) {
      window.scrollTo(0, 0);
    }
  }, [pathname]);

  return null;
}
