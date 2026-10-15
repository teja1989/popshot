// The main menu: five tabs at most, the most iOS and Android tab bars hold, so the same menu
// carries over to the apps (docs/adr/0006-navigation.md). Every page belongs to exactly one
// tab, which stays lit while you're on it. A tab behind a feature switch (migration 0027)
// shows only while that switch is on somewhere for you, so there's never an empty tab.
// Settings live under You; there's no catch-all "More".

export type NavIcon = "home" | "play" | "find" | "crew" | "you";

export interface NavItem {
  href: string;
  label: string;
  icon: NavIcon;
  // Shown only when this feature is on somewhere for you.
  feature?: string;
  matches: (pathname: string) => boolean;
}

// Pages under /groups/<id>: getting on court belongs to Play, the rest of the crew to Crew.
const GROUP = /^\/groups\/[^/]+/;
const PLAY_IN_GROUP = /^\/groups\/[^/]+\/(events|log|nights|matches)(\/|$)/;

export const NAV: readonly NavItem[] = [
  { href: "/", label: "Home", icon: "home", matches: (p) => p === "/" },
  { href: "/play", label: "Play", icon: "play", matches: (p) => p.startsWith("/play") || PLAY_IN_GROUP.test(p) },
  // Open crews near you. Its switch arrives with open crews; until then the tab stays hidden.
  { href: "/find", label: "Find", icon: "find", feature: "crew.open", matches: (p) => p.startsWith("/find") },
  {
    href: "/crew",
    label: "Crew",
    icon: "crew",
    matches: (p) => p.startsWith("/crew") || (GROUP.test(p) && !PLAY_IN_GROUP.test(p)),
  },
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
