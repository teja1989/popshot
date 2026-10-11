// Small, pure helpers for how people are shown.

// Google sign-in photos. The only image host the CSP allows besides the app itself.
const PHOTO_HOST = "lh3.googleusercontent.com";

export function initials(name: string | null | undefined): string {
  const trimmed = name?.trim() ?? "";
  if (!trimmed) {
    return "?";
  }
  const parts = trimmed.split(/\s+/);
  const first = parts[0] ?? "";
  const last = parts.length > 1 ? (parts[parts.length - 1] ?? "") : "";
  return (Array.from(first)[0] ?? "") + (Array.from(last)[0] ?? "") || "?";
}

/** The photo URL if it's one we can show, else null (initials are shown instead). */
export function usablePhoto(url: string | null | undefined): string | null {
  if (!url) {
    return null;
  }
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" && parsed.hostname === PHOTO_HOST ? parsed.href : null;
  } catch {
    return null;
  }
}

export function greetingFor(hour: number): string {
  if (hour >= 5 && hour < 12) {
    return "Good morning";
  }
  if (hour >= 12 && hour < 17) {
    return "Good afternoon";
  }
  return "Good evening";
}

export function firstName(displayName: string | null | undefined): string | null {
  const first = displayName?.trim().split(/\s+/)[0];
  // An empty name splits into [""]: treat that as no name.
  if (!first) {
    return null;
  }
  return first;
}
