import { parseReport, type ErrorReport } from "./error-report";

// The server side of crash reports (app/api/client-errors): checks a request, and writes
// one structured log line per report. Cloud Logging reads the JSON; the @type lets Error
// Reporting group repeats of the same error.

export const MAX_BYTES = 8 * 1024;
const PER_MINUTE = 120;

export type Outcome = { status: 204; report: ErrorReport } | { status: 400 | 403 | 413 | 415 | 429; detail: string };

/** Allows `limit` reports a minute on this instance; enough for real crashes, not a flood. */
export class RateLimit {
  private windowStart = 0;
  private count = 0;

  constructor(
    private readonly limit = PER_MINUTE,
    private readonly now: () => number = Date.now,
  ) {}

  take(): boolean {
    const now = this.now();
    if (now - this.windowStart >= 60_000) {
      this.windowStart = now;
      this.count = 0;
    }
    this.count += 1;
    return this.count <= this.limit;
  }
}

export async function receive(request: Request, limit: RateLimit): Promise<Outcome> {
  if (request.headers.get("sec-fetch-site") === "cross-site") {
    return { status: 403, detail: "Cross-site requests are not allowed." };
  }
  if (!request.headers.get("content-type")?.toLowerCase().startsWith("application/json")) {
    return { status: 415, detail: "Send JSON." };
  }
  const declared = Number(request.headers.get("content-length") ?? "0");
  if (declared > MAX_BYTES) {
    return { status: 413, detail: "That report is too large." };
  }
  const body = await request.text();
  if (body.length > MAX_BYTES) {
    return { status: 413, detail: "That report is too large." };
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(body);
  } catch {
    return { status: 400, detail: "That report isn't valid." };
  }
  const report = parseReport(parsed);
  if (report === null) {
    return { status: 400, detail: "That report isn't valid." };
  }
  if (!limit.take()) {
    return { status: 429, detail: "Too many reports." };
  }
  return { status: 204, report };
}

export function logLine(report: ErrorReport, userAgent: string | null, revision: string | undefined): string {
  const version = revision ?? "local";
  return JSON.stringify({
    severity: "ERROR",
    "@type": "type.googleapis.com/google.devtools.clouderrorreporting.v1beta1.ReportedErrorEvent",
    serviceContext: { service: "web-client", version },
    message: `${report.stack || `${report.name}: ${report.message}`}\n(ref ${report.ref})`,
    context: { httpRequest: { url: report.path, userAgent: (userAgent ?? "").slice(0, 200) } },
    event: "client_error",
    ref: report.ref,
    source: report.source,
    name: report.name,
    error: report.message,
    path: report.path,
    digest: report.digest,
  });
}
