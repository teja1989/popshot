import { describe, expect, it } from "vitest";

import { weekRange } from "./week";

// Intl puts thin spaces around the dash; compare with plain ones.
const plain = (text: string) => text.replace(/\s/g, " ");

describe("your week", () => {
  it("says which days it covers", () => {
    const until = new Date(2026, 9, 13, 9);
    const since = new Date(2026, 9, 6, 9);
    expect(plain(weekRange({ since: since.toISOString(), until: until.toISOString() }, "en-US"))).toBe("Oct 6 – 13");
  });

  it("spans a month end", () => {
    const until = new Date(2026, 9, 3, 9);
    const since = new Date(2026, 8, 26, 9);
    expect(plain(weekRange({ since: since.toISOString(), until: until.toISOString() }, "en-US"))).toBe(
      "Sep 26 – Oct 3",
    );
  });
});
