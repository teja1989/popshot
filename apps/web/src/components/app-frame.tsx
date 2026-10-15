"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion, useReducedMotion } from "motion/react";
import { useRef, type ReactNode } from "react";

import { NAV, tabColumns, visibleNav, type NavIcon } from "@/lib/nav";

import { CompactTitle } from "./compact-title";
import { useEverywhere } from "./features";
import { HashScroll } from "./hash-scroll";
import { onHomeLinkClick } from "./home-refresh";
import { SignOutButton } from "./sign-out-button";
import { Brand } from "./ui/brand";
import { CrewIcon, FindIcon, HomeIcon, PaddleIcon, YouIcon } from "./ui/icons";

// The signed-in frame: a sidebar on wide screens, a bottom tab bar on phones. The tabs are
// prefetched in full (Next.js keeps them 5 minutes): their pages hold no personal data (that
// loads in the browser), so a tap swaps the page without waiting for the server.

const ICONS: Record<NavIcon, ReactNode> = {
  home: <HomeIcon />,
  play: <PaddleIcon />,
  find: <FindIcon />,
  crew: <CrewIcon />,
  you: <YouIcon />,
};

export function AppFrame({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const nav = visibleNav(NAV, useEverywhere());
  const content = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion() ?? false;
  return (
    <div className="min-h-dvh lg:grid lg:grid-cols-[232px_minmax(0,1fr)]">
      {/* The column carries the background, so it runs the full height of long pages. */}
      <div className="hidden border-r border-line bg-surface lg:block">
        <aside className="sticky top-0 flex h-dvh flex-col gap-8 px-4 py-8">
          <Link
            href="/"
            aria-label="Popshot home"
            className="self-start rounded-xl px-2 py-1 text-ink no-underline"
            onClick={(event) => {
              onHomeLinkClick(pathname, event);
            }}
          >
            <Brand />
          </Link>
          <nav aria-label="Main">
            <ul className="flex flex-col gap-1">
              {nav.map((item) => {
                const active = item.matches(pathname);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      prefetch
                      aria-current={active ? "page" : undefined}
                      onClick={(event) => {
                        if (item.href === "/") {
                          onHomeLinkClick(pathname, event);
                        }
                      }}
                      className={`flex min-h-12 items-center gap-3 rounded-full px-4 text-lead font-bold no-underline transition-colors duration-150 ${active ? "bg-secondary-container text-on-secondary-container" : "text-muted hover:bg-surface-high hover:text-ink"}`}
                    >
                      {ICONS[item.icon]}
                      {item.label}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
          <div className="grow" />
          <SignOutButton className="w-full" />
        </aside>
      </div>

      <div ref={content} className="flex min-w-0 flex-col pb-24 lg:pb-0">
        <CompactTitle content={content} />
        <header className="px-5 pt-8 lg:hidden">
          <Link
            href="/"
            aria-label="Popshot home"
            className="inline-flex min-h-11 items-center text-ink no-underline"
            onClick={(event) => {
              onHomeLinkClick(pathname, event);
            }}
          >
            <Brand />
          </Link>
        </header>
        {/* Each page fades in (keyed by path: the frame itself stays put between pages).
            Opacity only: a moving transform here would shift the fixed Log a game button. */}
        <motion.div
          key={pathname}
          initial={reduced ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.18 }}
        >
          {children}
        </motion.div>
        <HashScroll />
      </div>

      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-30 bg-surface-high pb-[env(safe-area-inset-bottom)] lg:hidden"
      >
        <ul className={`mx-auto grid max-w-md ${tabColumns(nav.length)}`}>
          {nav.map((item) => {
            const active = item.matches(pathname);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  prefetch
                  aria-current={active ? "page" : undefined}
                  onClick={(event) => {
                    if (item.href === "/") {
                      onHomeLinkClick(pathname, event);
                    }
                  }}
                  className={`group flex min-h-16 flex-col items-center justify-center gap-1 pb-1 text-meta font-bold no-underline ${active ? "text-ink" : "text-muted"}`}
                >
                  {/* Material 3's navigation bar: a pill behind the chosen tab's icon. */}
                  <span
                    className={`flex h-8 w-14 items-center justify-center rounded-full transition-colors duration-200 ${active ? "bg-secondary-container text-on-secondary-container" : "group-hover:bg-surface-high"}`}
                  >
                    {ICONS[item.icon]}
                  </span>
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </div>
  );
}
