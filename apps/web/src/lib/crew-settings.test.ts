import { describe, expect, it } from "vitest";

import { planOf, sectionsFor } from "./crew-settings";
import type { GroupDetail } from "./groups";

function as(role: GroupDetail["my_role"], status: GroupDetail["my_status"]): GroupDetail {
  return { id: "g", my_role: role, my_status: status } as GroupDetail;
}

describe("crew settings sections", () => {
  it("leads and co-leads run the crew; everyone can leave", () => {
    expect(sectionsFor(as("lead", "active"))).toEqual(["crew", "court", "open", "profile", "rules", "leave"]);
    expect(sectionsFor(as("co_lead", "active"))).toEqual(["crew", "court", "open", "profile", "rules", "leave"]);
    expect(sectionsFor(as("member", "active"))).toEqual(["leave"]);
  });

  it("someone asking to join can only cancel", () => {
    expect(sectionsFor(as("member", "pending"))).toEqual(["leave"]);
  });

  it("everyone is on the free plan for now", () => {
    expect(planOf()).toBe("free");
  });
});
