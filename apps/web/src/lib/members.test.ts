import { describe, expect, it } from "vitest";

import { gamesCount, lastPlayed, memberLine } from "./members";

const NOW = new Date(2026, 9, 12, 18, 0);

describe("members", () => {
  it("says when someone last played, kindly", () => {
    expect(lastPlayed(null, NOW)).toBe("No games yet");
    expect(lastPlayed(new Date(2026, 9, 12, 9).toISOString(), NOW)).toBe("Played today");
    expect(lastPlayed(new Date(2026, 9, 11, 22).toISOString(), NOW)).toBe("Played yesterday");
    expect(lastPlayed(new Date(2026, 9, 9).toISOString(), NOW)).toBe("Played 3 days ago");
    expect(lastPlayed(new Date(2026, 2, 3).toISOString(), NOW, "en-US")).toBe("Played in March");
    expect(lastPlayed(new Date(2025, 2, 3).toISOString(), NOW, "en-US")).toBe("Played in March 2025");
  });

  it("puts joined and played together", () => {
    const member = { joined_at: new Date(2026, 2, 1).toISOString(), last_played_at: null };
    expect(memberLine(member, NOW, "en-US")).toBe("Joined March 2026 · No games yet");
    expect(memberLine({}, NOW)).toBe("No games yet");
  });

  it("counts games", () => {
    expect(gamesCount(0)).toBe("0 games");
    expect(gamesCount(1)).toBe("1 game");
  });
});
