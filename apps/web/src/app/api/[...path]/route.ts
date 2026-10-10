import { forward } from "@/lib/bff";
import { readServerConfig } from "@/lib/config";
import { ServiceIdentity } from "@/lib/service-auth";

export const dynamic = "force-dynamic";

let identity: { audience: string; client: ServiceIdentity } | null = null;

function serviceToken(audience: string | null): (() => Promise<string>) | null {
  if (audience === null) {
    return null;
  }
  if (identity?.audience !== audience) {
    identity = { audience, client: new ServiceIdentity(audience) };
  }
  const client = identity.client;
  return () => client.token();
}

interface Context {
  params: Promise<{ path: string[] }>;
}

async function handle(request: Request, context: Context): Promise<Response> {
  const config = readServerConfig();
  const { path } = await context.params;
  return forward(request, path, {
    apiBaseUrl: config.apiBaseUrl,
    serviceToken: serviceToken(config.apiAudience),
  });
}

export const GET = handle;
export const POST = handle;
export const PUT = handle;
export const PATCH = handle;
export const DELETE = handle;
