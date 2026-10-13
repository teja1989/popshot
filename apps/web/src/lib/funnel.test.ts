import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  arrivalSource,
  countVisit,
  forgetSource,
  rememberedSource,
  rememberSource,
  sourceFromParam,
  SOURCES,
  VISIT_PAGES,
} from "./funnel";

function memory(): Storage {
  const items = new Map<string, string>();
  return {
    get length() {
      return items.size;
    },
    clear: () => {
      items.clear();
    },
    getItem: (key) => items.get(key) ?? null,
    key: (i) => [...items.keys()][i] ?? null,
    removeItem: (key) => {
      items.delete(key);
    },
    setItem: (key, value) => {
      items.set(key, value);
    },
  };
}

function broken(): Storage {
  const fail = () => {
    throw new Error("blocked");
  };
  return { length: 0, clear: fail, getItem: fail, key: fail, removeItem: fail, setItem: fail };
}

describe("sources", () => {
  it("reads ?src= tags, and anything unknown is 'other'", () => {
    expect(sourceFromParam("reddit")).toBe("reddit");
    expect(sourceFromParam(" Poster ")).toBe("poster");
    expect(sourceFromParam("https://evil.example")).toBe("other");
    expect(sourceFromParam("")).toBeNull();
    expect(sourceFromParam(null)).toBeNull();
  });

  it("knows an invite link, and a tag beats the page", () => {
    expect(arrivalSource(new URL("https://p.example/join#abc"))).toBe("invite");
    expect(arrivalSource(new URL("https://p.example/join?src=poster#abc"))).toBe("poster");
    expect(arrivalSource(new URL("https://p.example/?src=recap"))).toBe("recap");
    expect(arrivalSource(new URL("https://p.example/games"))).toBeNull();
  });

  it("keeps the first source this browser saw", () => {
    const storage = memory();
    rememberSource("recap", storage);
    rememberSource("reddit", storage);
    expect(rememberedSource(storage)).toBe("recap");
    forgetSource(storage);
    expect(rememberedSource(storage)).toBeNull();
  });

  it("ignores anything else stored under its name", () => {
    const storage = memory();
    storage.setItem("popshot.source", "<script>");
    expect(rememberedSource(storage)).toBeNull();
    rememberSource("court", storage);
    expect(rememberedSource(storage)).toBe("court");
  });

  it("carries on without storage", () => {
    expect(() => {
      rememberSource("recap", broken());
    }).not.toThrow();
    expect(rememberedSource(broken())).toBeNull();
    expect(rememberedSource(null)).toBeNull();
  });

  it("match the API's lists", () => {
    // routes/funnel.py's SignupSource and VisitPage; a value missing on either side would
    // be refused.
    const source = readFileSync(
      fileURLToPath(new URL("../../../../services/api/src/popshot_api/routes/funnel.py", import.meta.url)),
      "utf8",
    );
    const literal = (name: string) =>
      [...(new RegExp(`${name} = Literal\\[([^\\]]*)\\]`).exec(source)?.[1] ?? "").matchAll(/"([a-z_]+)"/g)].map(
        (m) => m[1],
      );
    expect(literal("SignupSource")).toEqual([...SOURCES]);
    expect(literal("VisitPage")).toEqual([...VISIT_PAGES]);
  });
});

describe("countVisit", () => {
  it("sends a page once per tab", () => {
    const tab = memory();
    const sent: string[] = [];
    const send = (body: string) => sent.push(body);
    countVisit("home", "reddit", tab, send);
    countVisit("home", "reddit", tab, send);
    countVisit("recap_try", "direct", tab, send);
    expect(sent.map((b) => JSON.parse(b) as unknown)).toEqual([
      { page: "home", source: "reddit" },
      { page: "recap_try", source: "direct" },
    ]);
  });

  it("never throws, whatever the browser blocks", () => {
    expect(() => {
      countVisit("home", "direct", broken(), () => {
        throw new Error("offline");
      });
    }).not.toThrow();
  });
});
