import { describe, expect, it } from "vitest";

import { describeExpiry, tokenFromPasted, describeJoined, describeUses, inviteUrl, tokenFromHash } from "./invites";

const TOKEN = "Ab3_-".repeat(8) + "xyz";

describe("tokenFromHash", () => {
  it("reads a well-formed token, with or without the #", () => {
    expect(TOKEN).toHaveLength(43);
    expect(tokenFromHash(`#${TOKEN}`)).toBe(TOKEN);
    expect(tokenFromHash(TOKEN)).toBe(TOKEN);
  });

  it.each(["", "#", "#short", `#${TOKEN}x`, `#${TOKEN.slice(1)}!`, `#${TOKEN.slice(1)}%`, "#<script>"])(
    "rejects %j",
    (hash) => {
      expect(tokenFromHash(hash)).toBeNull();
    },
  );
});

describe("inviteUrl", () => {
  it("puts the token in the fragment", () => {
    expect(inviteUrl("https://popshot.example", TOKEN)).toBe(`https://popshot.example/join#${TOKEN}`);
  });
});

describe("describeUses", () => {
  it.each([
    [1, "For 1 person"],
    [5, "For up to 5 people"],
  ])("%i -> %s", (max_uses, expected) => {
    expect(describeUses({ max_uses })).toBe(expected);
  });
});

describe("describeJoined", () => {
  it.each([
    [0, "0 joined"],
    [1, "1 joined"],
    [4, "4 joined"],
  ])("%i -> %s", (use_count, expected) => {
    expect(describeJoined({ use_count })).toBe(expected);
  });
});

describe("describeExpiry", () => {
  const now = new Date("2026-10-11T12:00:00Z");
  it.each([
    ["2026-10-18T11:59:30Z", "Expires in 7 days"],
    ["2026-10-12T13:00:00Z", "Expires in 1 day"],
    ["2026-10-11T20:00:00Z", "Expires in 8 hours"],
    ["2026-10-11T12:30:00Z", "Expires within the hour"],
    ["2026-10-10T12:00:00Z", "Expires within the hour"],
  ])("%s -> %s", (expiresAt, expected) => {
    expect(describeExpiry(expiresAt, now)).toBe(expected);
  });
});

describe("tokenFromPasted", () => {
  it.each([
    [TOKEN, TOKEN],
    [`  ${TOKEN}\n`, TOKEN],
    [`https://popshot.example/join#${TOKEN}`, TOKEN],
    [`http://127.0.0.1:3000/join/#${TOKEN}`, TOKEN],
    [`Join my group: https://popshot.example/join#${TOKEN}`, TOKEN],
  ])("reads %j", (pasted, expected) => {
    expect(tokenFromPasted(pasted)).toBe(expected);
  });

  it.each([
    "",
    "hello",
    `https://popshot.example/join#${TOKEN}x`,
    `https://popshot.example/groups#${TOKEN}`,
    `https://popshot.example/join?t=${TOKEN}`,
    `javascript:alert(1)//join#${TOKEN.slice(1)}`,
  ])("rejects %j", (pasted) => {
    expect(tokenFromPasted(pasted)).toBeNull();
  });
});
