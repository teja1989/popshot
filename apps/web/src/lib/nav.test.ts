import { describe, expect, it } from "vitest";

import { NAV, tabColumns, visibleNav } from "./nav";

describe("main menu", () => {
  it("shows the four tabs, and Learn only while its switch is on", () => {
    const labels = (on: string[]) => visibleNav(NAV, new Set(on)).map((item) => item.label);
    expect(labels([])).toEqual(["Home", "Play", "Crew", "You"]);
    expect(labels(["recaps.ai"])).toEqual(["Home", "Play", "Crew", "You"]);
    expect(labels(["learn.tab"])).toEqual(["Home", "Play", "Crew", "Learn", "You"]);
  });

  it("knows which tab a page belongs to", () => {
    const active = (path: string) => NAV.filter((item) => item.matches(path)).map((item) => item.label);
    expect(active("/")).toEqual(["Home"]);
    expect(active("/groups/abc")).toEqual(["Home"]);
    expect(active("/groups/abc/recaps/def")).toEqual(["Crew"]);
    expect(active("/play")).toEqual(["Play"]);
    expect(active("/learn/drops")).toEqual(["Learn"]);
    expect(active("/you")).toEqual(["You"]);
  });

  it("gives the phone tab bar one column per tab", () => {
    expect(tabColumns(4)).toBe("grid-cols-4");
    expect(tabColumns(5)).toBe("grid-cols-5");
    expect(tabColumns(9)).toBe("grid-flow-col auto-cols-fr");
  });
});
