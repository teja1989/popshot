import { describe, expect, it } from "vitest";

import { cleanPath, newErrorRef, parseReport, REF_PATTERN, scrub } from "./error-report";

const valid = {
  ref: "K7Q2-M9XD",
  source: "page",
  name: "TypeError",
  message: "x is undefined",
  stack: "TypeError: x is undefined\n    at Page (https://web.example/_next/static/chunks/app/page-1a2b3c.js:1:200)",
  path: "/groups/1c09a78c-493a-429c-b3cc-203cdf3a83af/log",
  digest: null,
};

describe("newErrorRef", () => {
  it("is two groups of four, without I, L, O or U", () => {
    for (let i = 0; i < 200; i++) {
      const ref = newErrorRef();
      expect(ref).toMatch(REF_PATTERN);
      expect(ref).not.toMatch(/[ILOU]/);
    }
  });

  it("uses every random byte", () => {
    expect(newErrorRef(() => new Uint8Array([0, 1, 2, 3, 31, 32, 33, 255]))).toBe("0123-Z01Z");
  });
});

describe("scrub", () => {
  it("removes emails, IDs and tokens", () => {
    expect(scrub("no player casey@example.com", 100)).toBe("no player [email]");
    expect(scrub("group 1c09a78c-493a-429c-b3cc-203cdf3a83af gone", 100)).toBe("group :id gone");
    expect(scrub(`bad token ${"A".repeat(43)}`, 100)).toBe("bad token [token]");
  });

  it("drops a URL's query and fragment, where invite tokens live", () => {
    expect(scrub(`at https://popshot.app/join#${"t".repeat(43)} now`, 200)).toBe("at https://popshot.app/join now");
    expect(scrub("GET https://popshot.app/api/v1/x?start=2026", 200)).toBe("GET https://popshot.app/api/v1/x");
  });

  it("keeps script names in stack traces readable", () => {
    const line = "at f (https://web.example/_next/static/chunks/app/page-0123456789abcdef0123456789abcdef.js:1:2)";
    expect(scrub(line, 300)).toContain("page-0123456789abcdef0123456789abcdef.js");
  });

  it("strips control characters and stops at the limit", () => {
    expect(scrub("a\u0000b\u001bc", 10)).toBe("abc");
    expect(scrub("x ".repeat(50), 10)).toHaveLength(10);
  });
});

describe("cleanPath", () => {
  it("replaces IDs and drops anything after the path", () => {
    expect(cleanPath("/groups/1c09a78c-493a-429c-b3cc-203cdf3a83af/nights/8bbf35f3-79de-4d09-9d99-0aef448d8c82")).toBe(
      "/groups/:id/nights/:id",
    );
    expect(cleanPath("/join#secret")).toBe("/join");
    expect(cleanPath("games?x=1")).toBe("/games");
  });
});

describe("parseReport", () => {
  it("takes a well-formed report and cleans it again", () => {
    const report = parseReport({ ...valid, message: "no casey@example.com" });
    expect(report).toEqual({ ...valid, message: "no [email]", path: "/groups/:id/log" });
  });

  it.each([
    ["not an object", "x"],
    ["an array", [valid]],
    ["an extra field", { ...valid, userId: "u1" }],
    ["a bad ref", { ...valid, ref: "ILOU-0000" }],
    ["an unknown source", { ...valid, source: "server" }],
    ["a missing message", { ...valid, message: undefined }],
    ["a non-string stack", { ...valid, stack: 4 }],
    ["a bad digest", { ...valid, digest: "a b" }],
  ])("refuses %s", (_label, value) => {
    expect(parseReport(value)).toBeNull();
  });

  it("caps long fields", () => {
    const report = parseReport({ ...valid, message: "m ".repeat(5000), stack: "s ".repeat(5000) });
    expect(report?.message).toHaveLength(500);
    expect(report?.stack).toHaveLength(3000);
  });
});
