import { describe, expect, it } from "vitest";

import { NAV, tabColumns, visibleNav } from "./nav";

describe("main menu", () => {
  it("shows four tabs, and Find too while its switch is on: never more than five", () => {
    const labels = (on: string[]) => visibleNav(NAV, new Set(on)).map((item) => item.label);
    expect(labels([])).toEqual(["Home", "Play", "Crew", "You"]);
    expect(labels(["recaps.ai"])).toEqual(["Home", "Play", "Crew", "You"]);
    expect(labels(["crew.open"])).toEqual(["Home", "Play", "Find", "Crew", "You"]);
    expect(NAV.length).toBeLessThanOrEqual(5);
  });

  it("knows which tab a page belongs to", () => {
    const active = (path: string) => NAV.filter((item) => item.matches(path)).map((item) => item.label);
    expect(active("/")).toEqual(["Home"]);
    expect(active("/play")).toEqual(["Play"]);
    expect(active("/groups/abc/events/new")).toEqual(["Play"]);
    expect(active("/groups/abc/events/def")).toEqual(["Play"]);
    expect(active("/groups/abc/log")).toEqual(["Play"]);
    expect(active("/groups/abc/nights/def")).toEqual(["Play"]);
    expect(active("/groups/abc/matches/def/edit")).toEqual(["Play"]);
    expect(active("/find")).toEqual(["Find"]);
    expect(active("/crew")).toEqual(["Crew"]);
    expect(active("/groups/abc")).toEqual(["Crew"]);
    expect(active("/groups/abc/members")).toEqual(["Crew"]);
    expect(active("/groups/abc/settings")).toEqual(["Crew"]);
    expect(active("/groups/abc/recaps/def")).toEqual(["Crew"]);
    expect(active("/groups/abc/eventsy")).toEqual(["Crew"]);
    expect(active("/you")).toEqual(["You"]);
    expect(active("/you/journey")).toEqual(["You"]);
    expect(active("/you/settings")).toEqual(["You"]);
    // Pages outside the app's tabs light none.
    expect(active("/privacy")).toEqual([]);
  });

  it("gives the phone tab bar one column per tab", () => {
    expect(tabColumns(4)).toBe("grid-cols-4");
    expect(tabColumns(5)).toBe("grid-cols-5");
    expect(tabColumns(9)).toBe("grid-flow-col auto-cols-fr");
  });
});
