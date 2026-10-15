import { describe, expect, it } from "vitest";

import { BANNED } from "./copy-rules";
import { mapsUrl, newSession, pickProblem, searchText } from "./places";

describe("searchText", () => {
  it("waits for two characters and trims", () => {
    expect(searchText("")).toBeNull();
    expect(searchText(" r ")).toBeNull();
    expect(searchText("  ri ")).toBe("ri");
  });

  it("never sends more than the API takes", () => {
    expect(searchText("x".repeat(200))).toHaveLength(80);
  });
});

describe("mapsUrl", () => {
  it("links to the place by Google's ID, named as the crew names it", () => {
    const url = new URL(mapsUrl("ChIJ_ab-1", "Riverside courts") ?? "");
    expect(url.origin + url.pathname).toBe("https://www.google.com/maps/search/");
    expect(url.searchParams.get("api")).toBe("1");
    expect(url.searchParams.get("query")).toBe("Riverside courts");
    expect(url.searchParams.get("query_place_id")).toBe("ChIJ_ab-1");
  });

  it("is nothing without a real place ID", () => {
    expect(mapsUrl(null, "x")).toBeNull();
    expect(mapsUrl("", "x")).toBeNull();
    expect(mapsUrl("../evil", "x")).toBeNull();
    expect(mapsUrl("a&query=b", "x")).toBeNull();
    expect(mapsUrl("javascript:alert(1)", "x")).toBeNull();
  });

  it("escapes the crew's name", () => {
    const url = new URL(mapsUrl("abc", "A & B #1") ?? "");
    expect(url.searchParams.get("query")).toBe("A & B #1");
    expect(url.searchParams.get("query_place_id")).toBe("abc");
  });
});

describe("pickProblem", () => {
  it("says nothing on success and something friendly otherwise", () => {
    expect(pickProblem("saved")).toBeNull();
    for (const outcome of ["not_found", "unavailable"] as const) {
      const words = pickProblem(outcome) ?? "";
      expect(words).not.toBe("");
      expect(words).not.toMatch(BANNED);
    }
  });
});

describe("newSession", () => {
  it("is a fresh UUID each time", () => {
    const a = newSession();
    expect(a).toMatch(/^[0-9a-f-]{36}$/);
    expect(newSession()).not.toBe(a);
  });
});
