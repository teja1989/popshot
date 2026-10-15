import { describe, expect, it } from "vitest";

import { canonicalRedirect } from "./canonical";

const CANONICAL = "popshotpb.com";
const url = (path: string) => new URL(path, "http://0.0.0.0:8080");
const headers = (values: Record<string, string>) => new Headers(values);

describe("canonicalRedirect", () => {
  it("sends the run.app address to the domain, keeping the path and query", () => {
    const to = canonicalRedirect(url("/r/abc?x=1"), headers({ host: "web-123.us-east4.run.app" }), CANONICAL);
    expect(to?.href).toBe("https://popshotpb.com/r/abc?x=1");
  });

  it("sends Hosting's own web.app address too", () => {
    const to = canonicalRedirect(
      url("/you"),
      headers({ host: "web-123.us-east4.run.app", "x-forwarded-host": "popshot-web.web.app" }),
      CANONICAL,
    );
    expect(to?.href).toBe("https://popshotpb.com/you");
  });

  it("serves the page when it was reached on the domain", () => {
    expect(
      canonicalRedirect(
        url("/"),
        headers({ host: "web-123.us-east4.run.app", "x-forwarded-host": "popshotpb.com" }),
        CANONICAL,
      ),
    ).toBeNull();
    expect(canonicalRedirect(url("/"), headers({ host: "PopshotPB.com:443" }), CANONICAL)).toBeNull();
  });

  it("only goes to the domain, whatever a forwarded header says", () => {
    const to = canonicalRedirect(url("/"), headers({ "x-forwarded-host": "evil.example, popshotpb.com" }), CANONICAL);
    expect(to?.origin).toBe("https://popshotpb.com");
  });

  it("does nothing without a canonical host, or on this machine", () => {
    expect(canonicalRedirect(url("/"), headers({ host: "web-123.us-east4.run.app" }), null)).toBeNull();
    expect(canonicalRedirect(url("/"), headers({ host: "localhost:3000" }), CANONICAL)).toBeNull();
    expect(canonicalRedirect(url("/"), headers({ host: "127.0.0.1:8080" }), CANONICAL)).toBeNull();
  });
});
