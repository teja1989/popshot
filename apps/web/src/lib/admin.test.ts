import { describe, expect, it } from "vitest";

import { actionSummary, membership, reachedWeeks, share, shortDate } from "./admin";

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

describe("support history", () => {
  it("says what happened", () => {
    const base = { created_at: "2026-10-11T20:00:00Z", admin_name: "Admin", reason: "x", details: {} };
    expect(actionSummary({ ...base, action: "crew.lead_changed", target_user_id: "u", target_name: "Sam" })).toBe(
      "Admin made Sam the lead",
    );
    expect(actionSummary({ ...base, action: "crew.something_new", target_user_id: null, target_name: null })).toBe(
      "Admin: crew.something_new",
    );
  });
});
