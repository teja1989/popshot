// A crew's time zone (migration 0040): its days follow this clock. The lead's browser sends
// its own zone when a crew is made, and fills it in once for older crews.

import type { GroupDetail } from "./groups";

// The API's own check (routes/groups.py TimeZone); the database then keeps only zones it knows.
const ZONE = /^[A-Za-z][A-Za-z0-9_+/-]{0,63}$/;

export function isZoneName(value: unknown): value is string {
  return typeof value === "string" && ZONE.test(value);
}

/** This device's IANA time zone, such as "America/New_York", or null when it can't say. */
export function browserTimeZone(intl: Pick<typeof Intl, "DateTimeFormat"> = Intl): string | null {
  try {
    const zone = intl.DateTimeFormat().resolvedOptions().timeZone;
    return isZoneName(zone) ? zone : null;
  } catch {
    return null;
  }
}

/** Whether to fill in the crew's zone from this device: a lead or co-lead, and none yet. */
export function shouldFillTimeZone(group: GroupDetail, zone: string | null): zone is string {
  return (
    zone !== null &&
    !group.time_zone &&
    group.my_status === "active" &&
    (group.my_role === "lead" || group.my_role === "co_lead")
  );
}

/** "America/New_York" → "America / New York". */
export function zoneLabel(zone: string): string {
  return zone.replaceAll("_", " ").replaceAll("/", " / ");
}

/** The zones to pick from: what this browser knows, plus the crew's own, sorted. */
export function zoneChoices(current: string | null | undefined, known: readonly string[]): string[] {
  const zones = new Set(known.filter(isZoneName));
  if (current && isZoneName(current)) zones.add(current);
  return [...zones].sort((a, b) => a.localeCompare(b));
}

/** Every zone this browser knows, or none when it can't list them. */
export function knownZones(): string[] {
  try {
    return Intl.supportedValuesOf("timeZone");
  } catch {
    return [];
  }
}
