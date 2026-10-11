import { describe, expect, it } from "vitest";

import { defaultStart, myStatus, nightWhen, ordinal, spotsLine } from "./nights";

const person = (name: string) => ({ user_id: name, display_name: name, avatar_url: null });

describe("play nights", () => {
  const now = new Date(2026, 9, 11, 12);

  it("says when", () => {
    expect(nightWhen(new Date(2026, 9, 11, 18).toISOString(), now, "en-US")).toBe("Today · 6:00 PM");
    expect(nightWhen(new Date(2026, 9, 12, 9, 30).toISOString(), now, "en-US")).toBe("Tomorrow · 9:30 AM");
    expect(nightWhen(new Date(2026, 9, 15, 18).toISOString(), now, "en-US")).toBe("Thu, Oct 15 · 6:00 PM");
  });

  it("counts spots", () => {
    expect(spotsLine({ going: [person("A")], waitlist: [], spots: null })).toBe("1 going");
    expect(spotsLine({ going: [person("A")], waitlist: [], spots: 2 })).toBe("1 going · 1 spot left");
    expect(spotsLine({ going: [person("A"), person("B")], waitlist: [], spots: 2 })).toBe("Full");
    expect(spotsLine({ going: [person("A"), person("B")], waitlist: [person("C")], spots: 2 })).toBe("Full · 1 waiting");
  });

  it("says where you stand", () => {
    expect(myStatus({ my_answer: "in", my_waitlist_position: 2 })).toBe("You're 2nd on the waitlist");
    expect(myStatus({ my_answer: "in", my_waitlist_position: null })).toBe("You're in");
    expect(myStatus({ my_answer: null, my_waitlist_position: null })).toBeNull();
  });

  it.each([
    [1, "1st"],
    [2, "2nd"],
    [3, "3rd"],
    [4, "4th"],
    [11, "11th"],
    [12, "12th"],
    [13, "13th"],
    [21, "21st"],
    [22, "22nd"],
  ])("ordinal(%d)", (n, expected) => {
    expect(ordinal(n)).toBe(expected);
  });

  it("defaults to tomorrow at 6pm", () => {
    expect(defaultStart(now)).toEqual(new Date(2026, 9, 12, 18, 0));
  });
});
