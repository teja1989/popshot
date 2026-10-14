"use client";

import { useEffect, useState, type RefObject } from "react";

/**
 * On phones: once a page's big title has scrolled off the top, a slim bar slides in with the
 * same title, so you always know where you are (like iOS's large titles). Visual only: the
 * real heading is still on the page for screen readers.
 */
export function CompactTitle({ content }: { content: RefObject<HTMLElement | null> }) {
  const [title, setTitle] = useState("");
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const root = content.current;
    if (!root) {
      return;
    }
    let heading: Element | null = null;
    let watcher: IntersectionObserver | null = null;
    // Pages draw their title once their data arrives, and can change it: follow it.
    const attach = () => {
      const next = root.querySelector("main h1");
      if (next) {
        setTitle(next.textContent);
      }
      if (next === heading) {
        return;
      }
      watcher?.disconnect();
      heading = next;
      setShown(false);
      if (!next) {
        return;
      }
      watcher = new IntersectionObserver(([entry]) => {
        setShown(entry !== undefined && !entry.isIntersecting && entry.boundingClientRect.top < 0);
      });
      watcher.observe(next);
    };
    const changes = new MutationObserver(attach);
    changes.observe(root, { childList: true, subtree: true, characterData: true });
    attach();
    return () => {
      changes.disconnect();
      watcher?.disconnect();
    };
  }, [content]);

  return (
    <div
      aria-hidden="true"
      data-compact-title=""
      data-shown={shown ? "" : undefined}
      className={`fixed inset-x-0 top-0 z-20 bg-bg/95 pt-[env(safe-area-inset-top)] shadow-card backdrop-blur transition-transform duration-200 ease-court lg:hidden ${shown ? "translate-y-0" : "-translate-y-full"}`}
    >
      <p className="mx-auto max-w-md truncate px-5 py-3 text-title-sm font-bold text-ink">{title}</p>
    </div>
  );
}
