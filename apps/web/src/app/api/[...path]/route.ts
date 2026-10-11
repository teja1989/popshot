import { forward, upstreamFor } from "@/lib/bff";
import { readServerConfig } from "@/lib/config";
import { ServiceIdentity } from "@/lib/service-auth";

export const dynamic = "force-dynamic";

// One identity client per audience (the API, the admin service), each caching its token.
const identities = new Map<string, ServiceIdentity>();

function serviceToken(audience: string | null): (() => Promise<string>) | null {
  if (audience === null) {
    return null;
  }
  let client = identities.get(audience);
  if (!client) {
    client = new ServiceIdentity(audience);
    identities.set(audience, client);
  }
  const identity = client;
  return () => identity.token();
}

interface Context {
  params: Promise<{ path: string[] }>;
}

async function handle(request: Request, context: Context): Promise<Response> {
  const config = readServerConfig();
  const { path } = await context.params;
  const upstream = upstreamFor(path, config);
  if (upstream === null) {
    return Response.json({ detail: "Not found." }, { status: 404, headers: { "cache-control": "no-store" } });
  }
  return forward(request, path, {
    apiBaseUrl: upstream.baseUrl,
    serviceToken: serviceToken(upstream.audience),
  });
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
