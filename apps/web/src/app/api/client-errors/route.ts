import { logLine, RateLimit, receive } from "@/lib/client-errors";

export const dynamic = "force-dynamic";

const limit = new RateLimit();
const NO_STORE = { "cache-control": "no-store" };

// Crash reports from the browser (lib/report-error.ts). Anyone can call this, signed in or
// not, so it takes only small, well-formed reports, cleans them again, and caps the rate.
export async function POST(request: Request): Promise<Response> {
  const outcome = await receive(request, limit);
  if (outcome.status !== 204) {
    return Response.json({ detail: outcome.detail }, { status: outcome.status, headers: NO_STORE });
  }
  // One JSON line on stderr: Cloud Logging picks up the severity and fields.
  console.error(logLine(outcome.report, request.headers.get("user-agent"), process.env.K_REVISION));
  return new Response(null, { status: 204, headers: NO_STORE });
}
