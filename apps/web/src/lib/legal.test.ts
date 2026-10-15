import { describe, expect, it } from "vitest";

import { isDraft, updatedOn } from "./legal";

describe("isDraft", () => {
  it("is a draft while any placeholder is left", () => {
    expect(isDraft()).toBe(true);
    expect(isDraft({ company: "[Company name] LLC", state: "Virginia", contactEmail: "hi@popshot.app" })).toBe(true);
    expect(isDraft({ company: "Rally Labs LLC", state: "[State]", contactEmail: "hi@popshot.app" })).toBe(true);
    expect(isDraft({ company: "Rally Labs LLC", state: "Virginia", contactEmail: "hello@example.com" })).toBe(true);
    // Our real address, with the company details still to come.
    expect(isDraft({ company: "[Company name] LLC", state: "[State]", contactEmail: "hello@popshotpb.com" })).toBe(
      true,
    );
  });

  it("isn't once the real details are in", () => {
    expect(isDraft({ company: "Rally Labs LLC", state: "Virginia", contactEmail: "hi@popshot.app" })).toBe(false);
  });
});

describe("updatedOn", () => {
  it("reads as a date, whatever the server's time zone", () => {
    expect(updatedOn("2026-10-12")).toBe("October 12, 2026");
  });
});
