"use client";

// "Add to home screen". Chrome and Android fire beforeinstallprompt once, early, and let the
// page show the install dialog later; this module keeps that event. iPhone has no such event:
// the banner explains the Share menu instead.

interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

let deferred: InstallPromptEvent | null = null;
const listeners = new Set<() => void>();

function changed() {
  for (const listener of listeners) {
    listener();
  }
}

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferred = event as InstallPromptEvent;
    changed();
  });
  window.addEventListener("appinstalled", () => {
    deferred = null;
    changed();
  });
}

export function subscribeInstall(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function canPromptInstall(): boolean {
  return deferred !== null;
}

/** Show the browser's install dialog. True if they installed. */
export async function promptInstall(): Promise<boolean> {
  const event = deferred;
  if (!event) {
    return false;
  }
  deferred = null;
  changed();
  await event.prompt();
  return (await event.userChoice).outcome === "accepted";
}

const DISMISSED_KEY = "popshot.install-dismissed";
const DISMISS_DAYS = 30;

type KeyValue = Pick<Storage, "getItem" | "setItem">;

function browserStorage(): KeyValue {
  return localStorage;
}

export function installDismissed(now: number = Date.now(), storage: () => KeyValue = browserStorage): boolean {
  try {
    const at = Number(storage().getItem(DISMISSED_KEY));
    return Number.isFinite(at) && at > 0 && now - at < DISMISS_DAYS * 86_400_000;
  } catch {
    return false;
  }
}

export function dismissInstall(now: number = Date.now(), storage: () => KeyValue = browserStorage): void {
  try {
    storage().setItem(DISMISSED_KEY, String(now));
  } catch {
    // Storage blocked: the banner comes back next visit, which is fine.
  }
}
