import { describe, expect, it } from "vitest";

import { dismissInstall, installDismissed } from "./install";

function memory() {
  const values = new Map<string, string>();
  const store = {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => {
      values.set(key, value);
    },
  };
  return () => store;
}

describe("install banner dismissal", () => {
  it("stays hidden for 30 days after Not now", () => {
    const storage = memory();
    const now = Date.UTC(2026, 9, 11);
    expect(installDismissed(now, storage)).toBe(false);
    dismissInstall(now, storage);
    expect(installDismissed(now + 29 * 86_400_000, storage)).toBe(true);
    expect(installDismissed(now + 31 * 86_400_000, storage)).toBe(false);
  });

  it("treats blocked storage as not dismissed", () => {
    const blocked = () => {
      throw new Error("SecurityError");
    };
    expect(installDismissed(Date.now(), blocked)).toBe(false);
    expect(() => {
      dismissInstall(Date.now(), blocked);
    }).not.toThrow();
  });
});
