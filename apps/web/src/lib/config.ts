// Server-side runtime configuration. Read from the environment on each call so one
// built image can run in any environment. Nothing here is secret: the Firebase web
// config is public by design, and the API URL is internal-only on Cloud Run.

export interface FirebaseWebConfig {
  apiKey: string;
  authDomain: string;
  projectId: string;
  appId: string;
}

export interface ServerConfig {
  apiBaseUrl: URL;
  // Audience for the service-to-service identity token. Set on Cloud Run; unset locally.
  apiAudience: string | null;
  firebase: FirebaseWebConfig;
  // Local development only: host:port of the Firebase Auth emulator (dev/README.md).
  authEmulatorHost: string | null;
}

export class ConfigError extends Error {}

type Env = Record<string, string | undefined>;

function required(env: Env, name: string): string {
  const value = env[name]?.trim();
  if (!value) {
    throw new ConfigError(`${name} is not set`);
  }
  return value;
}

const HOSTNAME = /^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/;
const PROJECT_ID = /^[a-z][a-z0-9-]{4,28}[a-z0-9]$/;
const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);
const EMULATOR_HOST = /^(localhost|127\.0\.0\.1):[0-9]{2,5}$/;

export function parseApiBaseUrl(raw: string): URL {
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new ConfigError("API_BASE_URL is not a valid URL");
  }
  const local = LOCAL_HOSTS.has(url.hostname);
  if (url.protocol !== "https:" && !(local && url.protocol === "http:")) {
    throw new ConfigError("API_BASE_URL must use https (http is allowed only for localhost)");
  }
  if (url.username || url.password || url.search || url.hash) {
    throw new ConfigError("API_BASE_URL must not contain credentials, a query or a fragment");
  }
  if (url.pathname !== "/") {
    throw new ConfigError("API_BASE_URL must not contain a path");
  }
  return url;
}

export function readServerConfig(env: Env = process.env): ServerConfig {
  const authDomain = required(env, "FIREBASE_AUTH_DOMAIN").toLowerCase();
  if (!HOSTNAME.test(authDomain)) {
    throw new ConfigError("FIREBASE_AUTH_DOMAIN must be a bare hostname");
  }
  const projectId = required(env, "FIREBASE_PROJECT_ID");
  if (!PROJECT_ID.test(projectId)) {
    throw new ConfigError("FIREBASE_PROJECT_ID is not a valid project ID");
  }
  const audience = env.API_AUDIENCE?.trim() ?? "";
  return {
    authEmulatorHost: parseAuthEmulatorHost(env, projectId),
    apiBaseUrl: parseApiBaseUrl(required(env, "API_BASE_URL")),
    apiAudience: audience === "" ? null : audience,
    firebase: {
      apiKey: required(env, "FIREBASE_API_KEY"),
      authDomain,
      projectId,
      appId: required(env, "FIREBASE_APP_ID"),
    },
  };
}

// The emulator accepts made-up sign-ins, so it's refused anywhere but a developer's machine:
// loopback only, a demo-* project (Firebase's offline-only kind), and never on Cloud Run.
function parseAuthEmulatorHost(env: Env, projectId: string): string | null {
  const host = env.FIREBASE_AUTH_EMULATOR_HOST?.trim() ?? "";
  if (host === "") {
    return null;
  }
  if (!EMULATOR_HOST.test(host)) {
    throw new ConfigError("FIREBASE_AUTH_EMULATOR_HOST must be localhost:<port> or 127.0.0.1:<port>");
  }
  if (!projectId.startsWith("demo-")) {
    throw new ConfigError("FIREBASE_AUTH_EMULATOR_HOST needs a demo-* FIREBASE_PROJECT_ID");
  }
  if (env.K_SERVICE) {
    throw new ConfigError("FIREBASE_AUTH_EMULATOR_HOST can't be used on Cloud Run");
  }
  return host;
}
