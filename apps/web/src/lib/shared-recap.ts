// Server side only: reads a shared recap from the private API for the public card page and
// its preview image. The token goes in the request body, so it stays out of the API's logs.

import type { ServerConfig } from "./config";
import { ServiceIdentity } from "./service-auth";
import { SHARE_TOKEN, type SharedRecap } from "./shares";

const TIMEOUT_MS = 8000;

// One identity client, caching its token, for the API's audience.
let identity: ServiceIdentity | null = null;

function serviceToken(audience: string | null): Promise<string> | null {
  if (audience === null) {
    return null;
  }
  identity ??= new ServiceIdentity(audience);
  return identity.token();
}

export interface SharedRecapDeps {
  config: Pick<ServerConfig, "apiBaseUrl" | "apiAudience">;
  fetchFn?: typeof fetch;
  token?: (audience: string | null) => Promise<string> | null;
}

/** The recap behind a link, or null when the link is malformed, unknown, off or expired. */
export async function fetchSharedRecap(token: string, deps: SharedRecapDeps): Promise<SharedRecap | null> {
  if (!SHARE_TOKEN.test(token)) {
    return null;
  }
  const headers = new Headers({ "content-type": "application/json", accept: "application/json" });
  const service = (deps.token ?? serviceToken)(deps.config.apiAudience);
  if (service !== null) {
    headers.set("x-serverless-authorization", `Bearer ${await service}`);
  }
  const response = await (deps.fetchFn ?? fetch)(new URL("/v1/public/recap", deps.config.apiBaseUrl), {
    method: "POST",
    headers,
    body: JSON.stringify({ token }),
    redirect: "manual",
    cache: "no-store",
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`shared recap: API returned ${String(response.status)}`);
  }
  return (await response.json()) as SharedRecap;
}
