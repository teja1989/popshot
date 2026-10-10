import { describe, expect, it } from "vitest";

import { buildCsp, newNonce } from "./csp";

function directive(csp: string, name: string): string[] {
  const part = csp.split("; ").find((p) => p.startsWith(`${name} `));
  return part ? part.split(" ").slice(1) : [];
}

describe("buildCsp", () => {
  const prod = buildCsp({ nonce: "abc123", authDomain: "ps-dev.firebaseapp.com", dev: false });

  it("allows scripts only by nonce in production", () => {
    const scripts = directive(prod, "script-src");
    expect(scripts).toContain("'nonce-abc123'");
    expect(scripts).toContain("'strict-dynamic'");
    expect(scripts).not.toContain("'unsafe-inline'");
    expect(scripts).not.toContain("'unsafe-eval'");
  });

  it("locks down framing, plugins and base", () => {
    expect(directive(prod, "frame-ancestors")).toEqual(["'none'"]);
    expect(directive(prod, "object-src")).toEqual(["'none'"]);
    expect(directive(prod, "base-uri")).toEqual(["'none'"]);
    expect(directive(prod, "frame-src")).toEqual(["https://ps-dev.firebaseapp.com"]);
    expect(prod).toContain("upgrade-insecure-requests");
  });

  it("relaxes only what dev tooling needs", () => {
    const dev = buildCsp({ nonce: "n", authDomain: "a.example.com", dev: true });
    expect(directive(dev, "script-src")).toContain("'unsafe-eval'");
    expect(dev).not.toContain("upgrade-insecure-requests");
  });
});

describe("newNonce", () => {
  it("is random and long enough", () => {
    const nonces = new Set(Array.from({ length: 100 }, () => newNonce()));
    expect(nonces.size).toBe(100);
    for (const nonce of nonces) {
      expect(nonce).toMatch(/^[A-Za-z0-9+/]{22}==$/);
    }
  });
});
