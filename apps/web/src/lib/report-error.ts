import { cleanPath, LIMITS, newErrorRef, scrub, type ErrorReport, type ErrorSource } from "./error-report";

// Sends crash reports from the browser to /api/client-errors. A few per page load at most,
// and the same error twice gets the same reference instead of a second report.

const MAX_REPORTS = 5;
const sent = new Map<string, string>();

function describe(error: unknown): { name: string; message: string; stack: string } {
  if (error instanceof Error) {
    return { name: error.name || "Error", message: error.message, stack: error.stack ?? "" };
  }
  return { name: "Error", message: typeof error === "string" ? error : "Unknown error", stack: "" };
}

/**
 * Reports an error and returns its reference, to show to the person if there's a screen
 * for it. Never throws, and never reports its own failures.
 */
export function reportError(
  error: unknown,
  source: ErrorSource,
  options: { ref?: string; digest?: string | null } = {},
): string {
  const { name, message, stack } = describe(error);
  const key = `${source}|${name}|${message}`;
  const known = sent.get(key);
  if (known) {
    return known;
  }
  const ref = options.ref ?? newErrorRef();
  if (sent.size >= MAX_REPORTS) {
    return ref;
  }
  sent.set(key, ref);
  const report: ErrorReport = {
    ref,
    source,
    name: scrub(name, LIMITS.name),
    message: scrub(message, LIMITS.message),
    stack: scrub(stack, LIMITS.stack),
    path: cleanPath(window.location.pathname),
    digest: options.digest ?? null,
  };
  try {
    void fetch("/api/client-errors", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(report),
      keepalive: true,
    }).catch(() => undefined);
  } catch {
    // Reporting is best effort.
  }
  return ref;
}

/** For tests: forget what's been sent. */
export function resetReported(): void {
  sent.clear();
}
