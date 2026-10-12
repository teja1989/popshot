"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { onHomeLinkClick } from "./home-refresh";
import { SignOutButton } from "./sign-out-button";
import { Brand } from "./ui/brand";
import { BoardIcon, GamesIcon, HomeIcon, YouIcon } from "./ui/icons";

// The signed-in frame: a sidebar on wide screens, a bottom tab bar on phones.

const NAV = [
  { href: "/", label: "Home", icon: <HomeIcon />, matches: (p: string) => p === "/" || p.startsWith("/groups/") },
  { href: "/games", label: "Games", icon: <GamesIcon />, matches: (p: string) => p.startsWith("/games") },
  { href: "/board", label: "Board", icon: <BoardIcon />, matches: (p: string) => p.startsWith("/board") },
  { href: "/you", label: "You", icon: <YouIcon />, matches: (p: string) => p.startsWith("/you") },
] as const;

export function AppFrame({ children }: { children: ReactNode }) {
  const pathname = usePathname();
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
              {NAV.map((item) => {
                const active = item.matches(pathname);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      onClick={(event) => {
                        if (item.href === "/") {
                          onHomeLinkClick(pathname, event);
                        }
                      }}
                      className={`flex min-h-11 items-center gap-3 rounded-xl px-3 text-[16px] font-bold no-underline transition-colors duration-150 ${active ? "bg-chip text-primary" : "text-muted hover:bg-bg hover:text-ink"}`}
                    >
                      {item.icon}
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

      <div className="flex min-w-0 flex-col pb-24 lg:pb-0">
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
        {children}
      </div>

      <nav
        aria-label="Main"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-surface lg:hidden"
      >
        <ul className="mx-auto grid max-w-md grid-cols-4">
          {NAV.map((item) => {
            const active = item.matches(pathname);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  onClick={(event) => {
                    if (item.href === "/") {
                      onHomeLinkClick(pathname, event);
                    }
                  }}
                  className={`flex min-h-16 flex-col items-center justify-center gap-1 pb-1 text-[12px] font-bold no-underline ${active ? "text-primary" : "text-muted"}`}
                >
                  {item.icon}
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
