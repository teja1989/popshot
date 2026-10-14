"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { FEATURE } from "@/lib/journey";

import { useYouFeature } from "./features";
import { segmentLink, segmentTrack } from "./ui/segmented";

const TABS = [
  { href: "/you", label: "Me" },
  { href: "/you/journey", label: "Journey" },
] as const;

/** "Me | Journey" at the top of You, while your journey is switched on. Each is its own page. */
export function YouTabs() {
  const pathname = usePathname();
  const on = useYouFeature(FEATURE);
  if (!on) {
    return null;
  }
  return (
    <nav aria-label="You" className={`${segmentTrack} grid-cols-2`}>
      {TABS.map((tab) => (
        <Link
          key={tab.href}
          href={tab.href}
          aria-current={pathname === tab.href ? "page" : undefined}
          className={segmentLink}
        >
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}
