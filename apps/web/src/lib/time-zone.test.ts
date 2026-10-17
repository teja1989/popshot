import { describe, expect, it } from "vitest";

import { browserTimeZone, isZoneName, zoneChoices, zoneLabel } from "./time-zone";

function fakeIntl(zone: unknown) {
  return {
    DateTimeFormat: (() => ({ resolvedOptions: () => ({ timeZone: zone }) })) as unknown as typeof Intl.DateTimeFormat,
  };
}

describe("this device's zone", () => {
  it("reads it from the browser", () => {
    expect(browserTimeZone(fakeIntl("America/New_York"))).toBe("America/New_York");
    expect(browserTimeZone(fakeIntl("Etc/GMT+5"))).toBe("Etc/GMT+5");
  });

  it("gives up on anything that isn't a zone name", () => {
    for (const zone of [undefined, "", "../etc/passwd", "America/New York", "x".repeat(65), 7]) {
      expect(browserTimeZone(fakeIntl(zone))).toBeNull();
    }
    const broken = {
      DateTimeFormat: (() => {
        throw new Error("no Intl");
      }) as unknown as typeof Intl.DateTimeFormat,
    };
    expect(browserTimeZone(broken)).toBeNull();
  });

  it("matches the API's check", () => {
    expect(isZoneName("UTC")).toBe(true);
    expect(isZoneName("America/Argentina/Buenos_Aires")).toBe(true);
    expect(isZoneName("/UTC")).toBe(false);
  });
});

describe("picking one", () => {
  it("labels zones in plain words", () => {
    expect(zoneLabel("America/New_York")).toBe("America / New York");
    expect(zoneLabel("UTC")).toBe("UTC");
  });

  it("lists known zones sorted, with the crew's own even when this browser lacks it", () => {
    expect(zoneChoices("Europe/Kyiv", ["UTC", "Asia/Tokyo", "bad zone"])).toEqual(["Asia/Tokyo", "Europe/Kyiv", "UTC"]);
    expect(zoneChoices(null, ["UTC", "UTC"])).toEqual(["UTC"]);
  });
});
