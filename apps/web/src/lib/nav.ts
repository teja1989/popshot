// The main menu: Home, Play, Crew and You always; other tabs only while their feature switch
// is on (migration 0027) in at least one of your crews, so there's never an empty tab.

export type NavIcon = "home" | "play" | "crew" | "learn" | "you";

export interface NavItem {
  href: string;
  label: string;
  icon: NavIcon;
  // Shown only when this feature is on somewhere for you.
  feature?: string;
  matches: (pathname: string) => boolean;
}

// Recaps are opened from the Crew tab; events from Play.
const RECAP = /^\/groups\/[^/]+\/recaps\//;
const EVENT = /^\/groups\/[^/]+\/events(\/|$)/;

export const NAV: readonly NavItem[] = [
  {
    href: "/",
    label: "Home",
    icon: "home",
    matches: (p) => p === "/" || (p.startsWith("/groups/") && !RECAP.test(p) && !EVENT.test(p)),
  },
  { href: "/play", label: "Play", icon: "play", matches: (p) => p.startsWith("/play") || EVENT.test(p) },
  { href: "/crew", label: "Crew", icon: "crew", matches: (p) => p.startsWith("/crew") || RECAP.test(p) },
  // The shot library. Its page and switch arrive together; until then the switch doesn't exist.
  { href: "/learn", label: "Learn", icon: "learn", feature: "learn.tab", matches: (p) => p.startsWith("/learn") },
  { href: "/you", label: "You", icon: "you", matches: (p) => p.startsWith("/you") },
];

/** The tabs to show, given what's on for you anywhere (empty while it's still loading). */
export function visibleNav(items: readonly NavItem[], everywhere: ReadonlySet<string>): NavItem[] {
  return items.filter((item) => item.feature === undefined || everywhere.has(item.feature));
}

// Written out in full so Tailwind can see them (it doesn't evaluate code).
const COLUMNS: Record<number, string> = {
  3: "grid-cols-3",
  4: "grid-cols-4",
  5: "grid-cols-5",
  6: "grid-cols-6",
};

/** The phone tab bar's grid, one column per tab. */
export function tabColumns(count: number): string {
  return COLUMNS[count] ?? "grid-flow-col auto-cols-fr";
}
