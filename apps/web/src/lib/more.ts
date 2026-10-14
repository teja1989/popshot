// The More tab: everything Popshot does, in one list, so nothing hides behind the four main
// tabs. Only what works for you shows: crew items need a crew, switched features need their
// switch (migration 0027). Pure, so it's tested without a browser.

export type MoreSection = "play" | "crew" | "you" | "popshot";

export const SECTION_LABEL: Record<MoreSection, string> = {
  play: "Play",
  crew: "Your crew",
  you: "You",
  popshot: "Popshot",
};

export const SECTIONS: readonly MoreSection[] = ["play", "crew", "you", "popshot"];

// What an item does when tapped: open a page, or one of the actions the More page provides.
export type MoreAction = "start-crew" | "join-crew" | "sign-out";

export interface MoreItem {
  id: string;
  section: MoreSection;
  label: string;
  description: string;
  // Other words people might search for.
  keywords?: string;
  // A page, given the crew picked at the top (null when you have none).
  href?: (crewId: string | null) => string;
  action?: MoreAction;
  // Needs an active crew to make sense.
  crew?: boolean;
  // Shown only while this feature is on for the picked crew.
  feature?: string;
  // Marked "New" for NEW_DAYS after this date (YYYY-MM-DD).
  added?: string;
}

export const NEW_DAYS = 14;

// Headings on the pages these open; AppFrame scrolls to them once they've loaded.
export const MORE_ITEMS: readonly MoreItem[] = [
  {
    id: "log",
    section: "play",
    label: "Log a game",
    description: "Add a score. It counts toward stats, recaps and crew points.",
    keywords: "score result match record",
    crew: true,
    href: (crew) => `/groups/${crew ?? ""}/log`,
  },
  {
    id: "meetups",
    section: "play",
    label: "Meetups",
    description: "Plan a time to play, see who's in, and join the waitlist.",
    keywords: "rsvp schedule session night plan",
    crew: true,
    href: () => "/play#nights-heading",
  },
  {
    id: "events",
    section: "play",
    label: "Events",
    description: "Round robins and Ride the River: Popshot makes the rounds.",
    keywords: "round robin shuffle river tournament ladder",
    crew: true,
    feature: "events.*",
    added: "2026-10-13",
    href: () => "/play#events-heading",
  },
  {
    id: "games",
    section: "play",
    label: "Games and calendar",
    description: "Every game your crew has logged, by day.",
    keywords: "history matches calendar results",
    crew: true,
    href: () => "/play",
  },
  {
    id: "crew-home",
    section: "crew",
    label: "Crew page",
    description: "Your crew's profile, rules and what's coming up.",
    keywords: "group home",
    crew: true,
    href: (crew) => `/groups/${crew ?? ""}`,
  },
  {
    id: "members",
    section: "crew",
    label: "Members and invites",
    description: "Who's in, who's waiting, and inviting new people.",
    keywords: "invite people players guests join requests",
    crew: true,
    href: (crew) => `/groups/${crew ?? ""}/members`,
  },
  {
    id: "points",
    section: "crew",
    label: "Crew points and highlights",
    description: "How everyone's playing lately, and recaps of your outings.",
    keywords: "rating recap awards highlights",
    crew: true,
    href: () => "/crew",
  },
  {
    id: "settings",
    section: "crew",
    label: "Crew settings",
    description: "Name, game rules, profile, and leaving the crew.",
    keywords: "rules leave rename profile courts",
    crew: true,
    href: (crew) => `/groups/${crew ?? ""}/settings`,
  },
  {
    id: "stats",
    section: "you",
    label: "Your stats",
    description: "Streaks, close games, partners and your form.",
    keywords: "record wins partner nemesis head to head",
    href: () => "/you#stats-heading",
  },
  {
    id: "focus",
    section: "you",
    label: "Focus areas",
    description: "What you're good at and what you're working on.",
    keywords: "improve strengths goals skills",
    href: () => "/you#focus-heading",
  },
  {
    id: "week",
    section: "you",
    label: "Your week",
    description: "A friendly look at your last seven days, on Home.",
    keywords: "summary weekly",
    crew: true,
    href: () => "/",
  },
  {
    id: "notifications",
    section: "you",
    label: "Notifications",
    description: "Choose which reminders and updates you get.",
    keywords: "push alerts reminders mute",
    href: () => "/you#notify-heading",
  },
  {
    id: "code",
    section: "you",
    label: "Your invite code",
    description: "A code a lead can use to invite you straight in.",
    keywords: "code share",
    href: () => "/you#code-heading",
  },
  {
    id: "sharing",
    section: "you",
    label: "Shared recaps",
    description: "Whether your name shows on recap links people share.",
    keywords: "privacy share public",
    href: () => "/you#sharing-heading",
  },
  {
    id: "data",
    section: "you",
    label: "Your data",
    description: "Download a copy, or delete your account.",
    keywords: "export delete account privacy",
    href: () => "/you#data-heading",
  },
  {
    id: "start",
    section: "popshot",
    label: "Start a crew",
    description: "A new group for people you play with.",
    keywords: "create group new",
    action: "start-crew",
  },
  {
    id: "join",
    section: "popshot",
    label: "Join with an invite link",
    description: "Paste the link your crew's lead sent.",
    keywords: "join invite link",
    action: "join-crew",
  },
  {
    id: "help",
    section: "popshot",
    label: "Help and feedback",
    description: "Something not right, or an idea? A real person reads it.",
    keywords: "contact support bug feedback idea",
    href: () => "/contact",
  },
  {
    id: "privacy",
    section: "popshot",
    label: "Privacy",
    description: "What we keep and why.",
    href: () => "/privacy",
  },
  {
    id: "terms",
    section: "popshot",
    label: "Terms",
    description: "The rules for using Popshot.",
    href: () => "/terms",
  },
  {
    id: "sign-out",
    section: "popshot",
    label: "Sign out",
    description: "Sign out on this device.",
    keywords: "log out logout",
    action: "sign-out",
  },
];

export interface MoreContext {
  // The picked crew, if you have one.
  crewId: string | null;
  // Whether a feature is on for the picked crew.
  featureOn: (key: string) => boolean;
}

/** The items that work for you right now, in order. */
export function availableItems(items: readonly MoreItem[], context: MoreContext): MoreItem[] {
  return items.filter(
    (item) =>
      (!item.crew || context.crewId !== null) && (item.feature === undefined || context.featureOn(item.feature)),
  );
}

function normalise(text: string): string {
  return text.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");
}

/** Items matching every word of the search, in label, description or keywords. */
export function searchItems(items: readonly MoreItem[], query: string): MoreItem[] {
  const words = normalise(query).split(/\s+/).filter(Boolean);
  if (words.length === 0) {
    return [...items];
  }
  return items.filter((item) => {
    const haystack = normalise(`${item.label} ${item.description} ${item.keywords ?? ""}`);
    return words.every((word) => haystack.includes(word));
  });
}

/** Whether an item is still new on `today` (YYYY-MM-DD, local). */
export function isNew(item: MoreItem, today: string): boolean {
  if (!item.added) {
    return false;
  }
  const days = (Date.parse(`${today}T00:00:00Z`) - Date.parse(`${item.added}T00:00:00Z`)) / 86_400_000;
  return days >= 0 && days < NEW_DAYS;
}
