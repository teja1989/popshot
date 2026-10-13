// Where people come from (the API's migration 0024). The browser remembers the first source
// it sees until sign-up, then sends it once; arrival pages are counted anonymously.
// Nothing here identifies anyone: a source is one word from a fixed list, and a visit is a
// page name and that word.

// Kept in step with SignupSource and VisitPage in the API's routes/funnel.py (a test checks).
export const SOURCES = [
  "direct",
  "recap",
  "invite",
  "code",
  "reddit",
  "facebook",
  "nextdoor",
  "poster",
  "court",
  "partner",
  "other",
] as const;
export type Source = (typeof SOURCES)[number];

export const VISIT_PAGES = ["home", "recap", "recap_try", "invite"] as const;
export type VisitPage = (typeof VISIT_PAGES)[number];

const STORED = "popshot.source";
const SENT_PREFIX = "popshot.visit.";

export function isSource(value: unknown): value is Source {
  return typeof value === "string" && (SOURCES as readonly string[]).includes(value);
}

export function isVisitPage(value: unknown): value is VisitPage {
  return typeof value === "string" && (VISIT_PAGES as readonly string[]).includes(value);
}

/** A `?src=` value as a source: known words as they are, anything else "other", none null. */
export function sourceFromParam(raw: string | null): Source | null {
  const value = raw?.trim().toLowerCase() ?? "";
  if (value === "") {
    return null;
  }
  return isSource(value) ? value : "other";
}

/** Where this arrival came from: an explicit ?src= wins, then the page it landed on. */
export function arrivalSource(url: URL): Source | null {
  const tagged = sourceFromParam(url.searchParams.get("src"));
  if (tagged) {
    return tagged;
  }
  if (url.pathname === "/join") {
    return "invite";
  }
  return null;
}

// Storage can be missing or throw (private windows, blocked site data). Every use is optional.
function safely<T>(read: () => T): T | null {
  try {
    return read();
  } catch {
    return null;
  }
}

/** Keep the first source seen in this browser; later ones don't replace it. */
export function rememberSource(source: Source, storage: Storage | null = safely(() => localStorage)): void {
  safely(() => {
    if (storage && !isSource(storage.getItem(STORED))) {
      storage.setItem(STORED, source);
    }
  });
}

export function rememberedSource(storage: Storage | null = safely(() => localStorage)): Source | null {
  const value = safely(() => storage?.getItem(STORED) ?? null);
  return isSource(value) ? value : null;
}

export function forgetSource(storage: Storage | null = safely(() => localStorage)): void {
  safely(() => storage?.removeItem(STORED));
}

/**
 * Count a visit to an arrival page: once per tab per page, sent so it survives the page
 * being left straight away. Fails quietly; counting never gets in anyone's way.
 */
export function countVisit(
  page: VisitPage,
  source: Source,
  tab: Storage | null = safely(() => sessionStorage),
  send: (body: string) => void = beacon,
): void {
  const key = SENT_PREFIX + page;
  if (safely(() => tab?.getItem(key)) === "1") {
    return;
  }
  safely(() => tab?.setItem(key, "1"));
  safely(() => {
    send(JSON.stringify({ page, source }));
  });
}

function beacon(body: string): void {
  const blob = new Blob([body], { type: "application/json" });
  if (!navigator.sendBeacon("/api/visit", blob)) {
    void fetch("/api/visit", {
      method: "POST",
      body,
      headers: { "content-type": "application/json" },
      keepalive: true,
    });
  }
}
