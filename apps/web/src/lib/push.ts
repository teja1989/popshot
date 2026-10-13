"use client";

// Push notifications in the browser: whether they can work here, and turning them on/off.

import type { User } from "@firebase/auth";

import { apiPost } from "./api-client";

export interface PushConfig {
  public_key: string | null;
}

export interface NotificationSettings {
  categories: Category[];
  muted: Category[];
  devices: number;
}

export type Category = "games" | "play_nights" | "recaps" | "invites" | "requests" | "tab" | "milestones";

export const CATEGORY_LABEL: Record<Category, { title: string; body: string }> = {
  games: { title: "Games you played", body: "When someone logs a game you were in." },
  play_nights: { title: "Meetups", body: "New meetups, reminders and open spots." },
  recaps: { title: "Recaps", body: "When the recap of a game day you played in is ready." },
  invites: { title: "Invites", body: "When a crew invites you to join." },
  requests: { title: "Join requests", body: "When someone asks to join a crew you lead." },
  tab: { title: "Crew tab", body: "Expenses and settle-ups that involve you." },
  milestones: { title: "Milestones", body: "When you reach one." },
};

/** The categories this app knows how to show, in the API's order. The API may offer a
 *  newer one before the app has a label for it; that one is left out, never a crash. */
export function knownCategories(categories: readonly string[]): Category[] {
  return categories.filter((c): c is Category => Object.hasOwn(CATEGORY_LABEL, c));
}

const WORKER = "/sw.js";

export type PushSupport =
  | { kind: "ready" }
  // iPhone and iPad: push works only from the app on the home screen.
  | { kind: "install-first" }
  | { kind: "unsupported" };

export function isStandalone(): boolean {
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

export function isIos(userAgent: string = navigator.userAgent, touchPoints: number = navigator.maxTouchPoints): boolean {
  // iPadOS reports itself as a Mac; touch gives it away.
  return /iPhone|iPad|iPod/.test(userAgent) || (userAgent.includes("Macintosh") && touchPoints > 1);
}

export function pushSupport(): PushSupport {
  const capable = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  if (isIos() && !isStandalone()) {
    return { kind: "install-first" };
  }
  return capable ? { kind: "ready" } : { kind: "unsupported" };
}

/** The server's public key (base64url) as the bytes PushManager wants. */
export function keyBytes(base64url: string): Uint8Array<ArrayBuffer> {
  const padded = base64url.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (base64url.length % 4)) % 4);
  const raw = atob(padded);
  const bytes = new Uint8Array(new ArrayBuffer(raw.length));
  for (let i = 0; i < raw.length; i += 1) {
    bytes[i] = raw.charCodeAt(i);
  }
  return bytes;
}

async function registration(): Promise<ServiceWorkerRegistration> {
  await navigator.serviceWorker.register(WORKER, { scope: "/" });
  return navigator.serviceWorker.ready;
}

/** This device's subscription, if notifications are on here. */
export async function currentSubscription(): Promise<PushSubscription | null> {
  const existing = await navigator.serviceWorker.getRegistration("/");
  return existing ? existing.pushManager.getSubscription() : null;
}

/** Ask permission (if needed), subscribe this device and tell the server. */
export async function turnOn(user: User, publicKey: string): Promise<"on" | "denied"> {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    return "denied";
  }
  const reg = await registration();
  const sub =
    (await reg.pushManager.getSubscription()) ??
    (await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(publicKey) }));
  await apiPost(user, "/v1/me/push-subscriptions", sub.toJSON());
  return "on";
}

/** Unsubscribe this device and tell the server. */
export async function turnOff(user: User): Promise<void> {
  const sub = await currentSubscription();
  if (!sub) {
    return;
  }
  await apiPost(user, "/v1/me/push-subscriptions/remove", { endpoint: sub.endpoint });
  await sub.unsubscribe();
}
