import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { REF_PATTERN } from "./error-report";
import { reportError, resetReported } from "./report-error";

let fetchMock: Mock<(url: string, init: RequestInit) => Promise<Response>>;

beforeEach(() => {
  resetReported();
  fetchMock = vi.fn(() => Promise.resolve(new Response(null, { status: 204 })));
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("window", { location: { pathname: "/groups/1c09a78c-493a-429c-b3cc-203cdf3a83af" } });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function sentBody(call = 0): Record<string, unknown> {
  const init = fetchMock.mock.calls[call]?.[1] ?? {};
  return JSON.parse(init.body as string) as Record<string, unknown>;
}

describe("reportError", () => {
  it("sends a cleaned report and returns its reference", () => {
    const ref = reportError(new TypeError("no casey@example.com"), "window");
    expect(ref).toMatch(REF_PATTERN);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/client-errors",
      expect.objectContaining({ method: "POST", keepalive: true }),
    );
    expect(sentBody()).toMatchObject({
      ref,
      source: "window",
      name: "TypeError",
      message: "no [email]",
      path: "/groups/:id",
    });
  });

  it("uses the reference it's given, with the server's digest", () => {
    expect(reportError(new Error("boom"), "page", { ref: "AAAA-BBBB", digest: "123" })).toBe("AAAA-BBBB");
    expect(sentBody()).toMatchObject({ ref: "AAAA-BBBB", digest: "123" });
  });

  it("reports the same error once, with the same reference", () => {
    const first = reportError(new Error("again"), "promise");
    const second = reportError(new Error("again"), "promise");
    expect(second).toBe(first);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("sends at most five a page", () => {
    for (let i = 0; i < 8; i++) {
      expect(reportError(new Error(`e${String(i)}`), "window")).toMatch(REF_PATTERN);
    }
    expect(fetchMock).toHaveBeenCalledTimes(5);
  });

  it("copes with things that aren't errors, and with fetch failing", () => {
    fetchMock.mockImplementation(() => Promise.reject(new Error("offline")));
    expect(reportError("plain text", "promise")).toMatch(REF_PATTERN);
    expect(reportError({ odd: true }, "promise")).toMatch(REF_PATTERN);
    expect(sentBody(1)).toMatchObject({ name: "Error", message: "Unknown error" });
  });
});
