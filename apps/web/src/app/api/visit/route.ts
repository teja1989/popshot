import { readServerConfig } from "@/lib/config";
import { forwardVisit, receiveVisit, VisitLimits } from "@/lib/visit-counter";

export const dynamic = "force-dynamic";

const limits = new VisitLimits();
const NO_STORE = { "cache-control": "no-store" };

// Anonymous visit counts from arrival pages (lib/funnel.ts). Anyone can call this, so it
// takes only a known page and source, and caps how often. It answers the same whether or
// not the count was kept, so it tells a caller nothing.
export async function POST(request: Request): Promise<Response> {
  const outcome = await receiveVisit(request, limits);
  if (outcome.status !== 204) {
    return Response.json({ detail: outcome.detail }, { status: outcome.status, headers: NO_STORE });
  }
  try {
    await forwardVisit(outcome.visit, { config: readServerConfig() });
  } catch (error) {
    console.error(JSON.stringify({ severity: "WARNING", event: "visit_not_counted", error: String(error) }));
  }
  return new Response(null, { status: 204, headers: NO_STORE });
}
