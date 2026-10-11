import { describe, expect, it } from "vitest";

import { firstName, greetingFor, initials, usablePhoto } from "./people";

describe("initials", () => {
  it.each([
    ["Casey Morgan", "CM"],
    ["casey", "c"],
    ["  Jordan   Lee  Smith ", "JS"],
    ["Émile Zola", "ÉZ"],
    ["🏓 Crew", "🏓C"],
    ["", "?"],
    ["   ", "?"],
    [null, "?"],
    [undefined, "?"],
  ])("%j -> %j", (name, expected) => {
    expect(initials(name)).toBe(expected);
  });
});

describe("usablePhoto", () => {
  it("accepts Google sign-in photos", () => {
    const url = "https://lh3.googleusercontent.com/a/abc=s96-c";
    expect(usablePhoto(url)).toBe(url);
  });

  it.each([
    "http://lh3.googleusercontent.com/a/abc",
    "https://evil.example.com/a.png",
    "https://lh3.googleusercontent.com.evil.example/a.png",
    "https://user@evil.example/lh3.googleusercontent.com",
    "javascript:alert(1)",
    "data:image/png;base64,AAAA",
    "not a url",
    "",
  ])("rejects %j", (url) => {
    expect(usablePhoto(url)).toBeNull();
  });

  it("treats a missing photo as none", () => {
    expect(usablePhoto(null)).toBeNull();
    expect(usablePhoto(undefined)).toBeNull();
  });
});

describe("greetingFor", () => {
  it.each([
    [0, "Good evening"],
    [4, "Good evening"],
    [5, "Good morning"],
    [11, "Good morning"],
    [12, "Good afternoon"],
    [16, "Good afternoon"],
    [17, "Good evening"],
    [23, "Good evening"],
  ])("%i:00 -> %s", (hour, expected) => {
    expect(greetingFor(hour)).toBe(expected);
  });
});

describe("firstName", () => {
  it.each([
    ["Casey Morgan", "Casey"],
    ["  Alex  ", "Alex"],
    ["", null],
    ["   ", null],
    [null, null],
  ])("%j -> %j", (name, expected) => {
    expect(firstName(name)).toBe(expected);
  });
});
