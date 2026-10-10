// Identity token that proves to the API's Cloud Run service that the caller is the web
// service account. Fetched from the metadata server, which only exists on Google Cloud.
// It travels in X-Serverless-Authorization, leaving Authorization for the user's token.

const METADATA_URL =
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity";
const REFRESH_MARGIN_SECONDS = 300;

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

function expiryOf(token: string): number {
  const payload = token.split(".")[1];
  if (!payload) {
    throw new Error("identity token is not a JWT");
  }
  const json = JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as { exp?: unknown };
  if (typeof json.exp !== "number") {
    throw new Error("identity token has no exp");
  }
  return json.exp;
}

export class ServiceIdentity {
  private cached: { token: string; exp: number } | null = null;
  private inflight: Promise<string> | null = null;

  constructor(
    private readonly audience: string,
    private readonly fetchFn: FetchLike = fetch,
    private readonly now: () => number = () => Date.now() / 1000,
  ) {}

  async token(): Promise<string> {
    if (this.cached && this.cached.exp - REFRESH_MARGIN_SECONDS > this.now()) {
      return this.cached.token;
    }
    this.inflight ??= this.fetchToken().finally(() => {
      this.inflight = null;
    });
    return this.inflight;
  }

  private async fetchToken(): Promise<string> {
    const url = `${METADATA_URL}?audience=${encodeURIComponent(this.audience)}&format=full`;
    const response = await this.fetchFn(url, {
      headers: { "Metadata-Flavor": "Google" },
      signal: AbortSignal.timeout(3000),
    });
    if (!response.ok) {
      throw new Error(`metadata server returned ${String(response.status)}`);
    }
    const token = (await response.text()).trim();
    this.cached = { token, exp: expiryOf(token) };
    return token;
  }
}
