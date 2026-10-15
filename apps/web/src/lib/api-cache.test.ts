import { afterEach, describe, expect, it } from "vitest";

import { cacheable, cacheKey, cacheSize, clearCache, forget, readCache, writeCache } from "./api-cache";

afterEach(() => {
  clearCache();
});

describe("the in-memory API cache", () => {
  it("gives back what was stored, per account", () => {
    writeCache(cacheKey("ana", "/v1/groups"), ["Alpha"]);
    expect(readCache(cacheKey("ana", "/v1/groups"))).toEqual({ data: ["Alpha"] });
    expect(readCache(cacheKey("ben", "/v1/groups"))).toBeNull();
    expect(readCache(cacheKey("ana", "/v1/me/focus"))).toBeNull();
  });

  it("keeps a stored null or empty answer as an answer", () => {
    writeCache(cacheKey("ana", "/v1/me/story"), null);
    expect(readCache(cacheKey("ana", "/v1/me/story"))).toEqual({ data: null });
  });

  it("never keeps admin answers", () => {
    expect(cacheable("/v1/admin")).toBe(false);
    expect(cacheable("/v1/admin/overview")).toBe(false);
    expect(cacheable("/v1/admin?x=1")).toBe(false);
    expect(cacheable("/v1/groups")).toBe(true);
    expect(cacheable("/v1/administrators-club")).toBe(true);
  });

  it("forgets one answer when told to", () => {
    writeCache(cacheKey("ana", "/v1/groups/1"), "one");
    writeCache(cacheKey("ana", "/v1/groups/2"), "two");
    forget(cacheKey("ana", "/v1/groups/1"));
    expect(readCache(cacheKey("ana", "/v1/groups/1"))).toBeNull();
    expect(readCache(cacheKey("ana", "/v1/groups/2"))).toEqual({ data: "two" });
  });

  it("forgets everything on sign-out", () => {
    writeCache(cacheKey("ana", "/v1/groups"), []);
    clearCache();
    expect(readCache(cacheKey("ana", "/v1/groups"))).toBeNull();
    expect(cacheSize()).toBe(0);
  });

  it("stays small: the least recently used answer goes first", () => {
    for (let i = 0; i < 150; i++) {
      writeCache(cacheKey("ana", `/v1/groups/${String(i)}`), i);
    }
    // Reading the first one makes it recent, so the second is now the oldest.
    readCache(cacheKey("ana", "/v1/groups/0"));
    writeCache(cacheKey("ana", "/v1/groups/new"), "new");
    expect(cacheSize()).toBe(150);
    expect(readCache(cacheKey("ana", "/v1/groups/0"))).toEqual({ data: 0 });
    expect(readCache(cacheKey("ana", "/v1/groups/1"))).toBeNull();
  });
});
