import { describe, expect, it } from "vitest";

import { inviteLine, normalizeCode } from "./direct-invites";

describe("direct invites", () => {
  it("reads codes the way people type them", () => {
    expect(normalizeCode("k7m2-qx4p")).toBe("K7M2QX4P");
    expect(normalizeCode(" K7M2 QX4P ")).toBe("K7M2QX4P");
    expect(normalizeCode("OILZ-0000")).toBe("011Z0000");
    expect(normalizeCode("K7M2-QX4")).toBeNull();
    expect(normalizeCode("K7M2-QX4U")).toBeNull();
    expect(normalizeCode("")).toBeNull();
  });

  it("says who invited you and how big the crew is", () => {
    expect(inviteLine({ invited_by_name: "Casey", members: 4 })).toBe("Casey invited you · 4 members");
    expect(inviteLine({ invited_by_name: null, members: 1 })).toBe("You're invited · 1 member");
  });
});
