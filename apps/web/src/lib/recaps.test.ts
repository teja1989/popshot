import { describe, expect, it } from "vitest";

import { describeAward, outingSize, outingWindow, type Award } from "./recaps";

const jo = { player_id: "1", display_name: "Jo", is_guest: false };

describe("recaps", () => {
  it("names each award and says what it was for", () => {
    const award = (kind: Award["kind"], value: number): Award => ({ kind, players: [jo], value });
    expect(describeAward(award("always_there", 5))).toEqual({ title: "Always There", why: "5 weeks in a row" });
    expect(describeAward(award("great_partner", 3)).why).toBe("Won with 3 different partners");
    expect(describeAward(award("welcome_wagon", 1)).why).toBe("Partnered a first-timer");
    expect(describeAward(award("welcome_wagon", 2)).why).toBe("Partnered 2 first-timers");
    expect(describeAward(award("personal_best", 7)).why).toBe("7 games in one day, a new high");
    expect(describeAward(award("close_call", 2))).toEqual({ title: "Close Call", why: "Won a game by a point or two" });
  });

  it("asks the calendar for exactly the outing, even a single game", () => {
    const at = "2026-10-12T18:00:00.000Z";
    expect(outingWindow({ start: at, end: at })).toEqual({ start: at, end: "2026-10-12T18:00:01.000Z" });
  });

  it("sizes an outing", () => {
    expect(outingSize({ games: 1, players: 2 })).toBe("1 game · 2 players");
    expect(outingSize({ games: 6, players: 5 })).toBe("6 games · 5 players");
  });
});
