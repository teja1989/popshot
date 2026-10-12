import { describe, expect, it } from "vitest";

import { gamesText, namesText, SHARE_TOKEN, shareUrl, siteOrigin, teamAWon } from "./shares";

describe("shares", () => {
  it("names people, counting the ones who can't be named", () => {
    expect(namesText({ names: ["Jo"], more: 0 })).toBe("Jo");
    expect(namesText({ names: ["Jo", "Sam"], more: 0 })).toBe("Jo and Sam");
    expect(namesText({ names: ["Jo", "Sam", "Ana"], more: 0 })).toBe("Jo, Sam and Ana");
    expect(namesText({ names: ["Jo"], more: 1 })).toBe("Jo and 1 more");
    expect(namesText({ names: [], more: 1 })).toBe("A crew member");
    expect(namesText({ names: [], more: 2 })).toBe("2 crew members");
  });

  it("writes scores and finds the winner", () => {
    expect(gamesText([[11, 9]])).toBe("11–9");
    expect(
      gamesText([
        [11, 9],
        [8, 11],
        [11, 6],
      ]),
    ).toBe("11–9, 8–11 and 11–6");
    expect(teamAWon([[11, 9]])).toBe(true);
    expect(
      teamAWon([
        [11, 9],
        [8, 11],
        [6, 11],
      ]),
    ).toBe(false);
  });

  it("builds links on this site only from well-formed tokens", () => {
    const token = "a".repeat(43);
    expect(shareUrl("https://popshot.example", token)).toBe(`https://popshot.example/r/${token}`);
    expect(SHARE_TOKEN.test(token)).toBe(true);
    expect(SHARE_TOKEN.test("a".repeat(42))).toBe(false);
    expect(SHARE_TOKEN.test(`${"a".repeat(42)}/`)).toBe(false);
  });

  it("takes the site's origin from sane headers only", () => {
    expect(siteOrigin(new Headers({ host: "web.example.run.app" }))?.origin).toBe("https://web.example.run.app");
    expect(siteOrigin(new Headers({ host: "127.0.0.1:3200", "x-forwarded-proto": "http" }))?.origin).toBe(
      "http://127.0.0.1:3200",
    );
    expect(siteOrigin(new Headers({ host: "evil.example/path" }))).toBeNull();
    expect(siteOrigin(new Headers({ host: "a.example", "x-forwarded-proto": "javascript" }))).toBeNull();
    expect(siteOrigin(new Headers())).toBeNull();
  });
});
