import { describe, expect, it } from "vitest";

import { membership, reachedWeeks, share, shortDate } from "./admin";

describe("admin formatting", () => {
  it("shares", () => {
    expect(share(2, 5)).toBe("40%");
    expect(share(0, 3)).toBe("0%");
    expect(share(0, 0)).toBe("–");
  });

  it("dates in UTC", () => {
    expect(shortDate("2026-10-05")).toBe("Oct 5");
    expect(shortDate("2026-10-05T23:30:00Z")).toBe("Oct 5");
  });

  it("only shows retention weeks a cohort has reached", () => {
    const monday = "2026-09-28";
    expect(reachedWeeks(monday, new Date("2026-10-01T12:00:00Z"))).toBe(0);
    expect(reachedWeeks(monday, new Date("2026-10-05T00:00:00Z"))).toBe(1);
    expect(reachedWeeks(monday, new Date("2026-11-30T00:00:00Z"))).toBe(4);
  });
});

describe("membership labels", () => {
  it.each([
    [{ role: "lead", status: "active", left_on_own: false }, "Lead"],
    [{ role: "co_lead", status: "active", left_on_own: false }, "Co-lead"],
    [{ role: "member", status: "pending", left_on_own: false }, "Asked to join"],
    [{ role: "member", status: "removed", left_on_own: true }, "Left"],
    [{ role: "member", status: "removed", left_on_own: false }, "Removed"],
  ] as const)("%o is %s", (m, label) => {
    expect(membership(m)).toBe(label);
  });
});
