import { describe, expect, it } from "vitest";

import { ConfigError, parseApiBaseUrl, readServerConfig } from "./config";

const BASE = {
  API_BASE_URL: "https://api-xyz.a.run.app",
  FIREBASE_API_KEY: "key",
  FIREBASE_AUTH_DOMAIN: "ps-dev-1234.firebaseapp.com",
  FIREBASE_PROJECT_ID: "ps-dev-1234",
  FIREBASE_APP_ID: "1:2:web:3",
};

describe("readServerConfig", () => {
  it("reads a complete config", () => {
    const config = readServerConfig({ ...BASE, API_AUDIENCE: "https://api-xyz.a.run.app" });
    expect(config.apiBaseUrl.href).toBe("https://api-xyz.a.run.app/");
    expect(config.apiAudience).toBe("https://api-xyz.a.run.app");
    expect(config.firebase.projectId).toBe("ps-dev-1234");
  });

  it("has no admin service unless one is set", () => {
    expect(readServerConfig(BASE).adminApi).toBeNull();
    const config = readServerConfig({
      ...BASE,
      ADMIN_API_BASE_URL: "https://admin-xyz.a.run.app",
      ADMIN_API_AUDIENCE: "https://admin-xyz.a.run.app",
    });
    expect(config.adminApi?.baseUrl.href).toBe("https://admin-xyz.a.run.app/");
    expect(config.adminApi?.audience).toBe("https://admin-xyz.a.run.app");
  });

  it("checks the admin service URL like the API's", () => {
    expect(() => readServerConfig({ ...BASE, ADMIN_API_BASE_URL: "http://admin.example.com" })).toThrow(
      /ADMIN_API_BASE_URL must use https/,
    );
  });

  it("treats a blank audience as unset", () => {
    expect(readServerConfig({ ...BASE, API_AUDIENCE: " " }).apiAudience).toBeNull();
  });

  it.each(Object.keys(BASE))("requires %s", (name) => {
    expect(() => readServerConfig({ ...BASE, [name]: "" })).toThrow(ConfigError);
  });

  it.each(["evil.com/x", "https://evil.com", "a b", "x.firebaseapp.com'; script-src *"])(
    "rejects auth domain %j",
    (value) => {
      expect(() => readServerConfig({ ...BASE, FIREBASE_AUTH_DOMAIN: value })).toThrow(ConfigError);
    },
  );
});

describe("parseApiBaseUrl", () => {
  it.each(["http://localhost:8000", "http://127.0.0.1:4010", "https://api.example.com"])("accepts %s", (value) => {
    expect(() => parseApiBaseUrl(value)).not.toThrow();
  });

  it.each([
    "http://api.example.com",
    "https://user:pw@api.example.com",
    "https://api.example.com/v1",
    "https://api.example.com/?a=1",
    "ftp://api.example.com",
    "not a url",
  ])("rejects %s", (value) => {
    expect(() => parseApiBaseUrl(value)).toThrow(ConfigError);
  });
});

describe("FIREBASE_AUTH_EMULATOR_HOST", () => {
  const LOCAL = { ...BASE, FIREBASE_PROJECT_ID: "demo-popshot", API_BASE_URL: "http://127.0.0.1:8000" };

  it("is off unless set", () => {
    expect(readServerConfig(LOCAL).authEmulatorHost).toBeNull();
    expect(readServerConfig({ ...LOCAL, FIREBASE_AUTH_EMULATOR_HOST: " " }).authEmulatorHost).toBeNull();
  });

  it.each(["127.0.0.1:9099", "localhost:9099"])("accepts %s for a demo project", (host) => {
    expect(readServerConfig({ ...LOCAL, FIREBASE_AUTH_EMULATOR_HOST: host }).authEmulatorHost).toBe(host);
  });

  it.each(["emulator:9099", "10.0.0.5:9099", "127.0.0.1", "http://127.0.0.1:9099", "127.0.0.1:9099/x"])(
    "rejects host %j",
    (host) => {
      expect(() => readServerConfig({ ...LOCAL, FIREBASE_AUTH_EMULATOR_HOST: host })).toThrow(ConfigError);
    },
  );

  it("refuses a real project", () => {
    expect(() => readServerConfig({ ...BASE, FIREBASE_AUTH_EMULATOR_HOST: "127.0.0.1:9099" })).toThrow(/demo-/);
  });

  it("refuses Cloud Run", () => {
    expect(() =>
      readServerConfig({ ...LOCAL, FIREBASE_AUTH_EMULATOR_HOST: "127.0.0.1:9099", K_SERVICE: "web" }),
    ).toThrow(/Cloud Run/);
  });
});

describe("CANONICAL_HOST", () => {
  it("is off unless set", () => {
    expect(readServerConfig(BASE).canonicalHost).toBeNull();
    expect(readServerConfig({ ...BASE, CANONICAL_HOST: " " }).canonicalHost).toBeNull();
  });

  it("is a bare hostname", () => {
    expect(readServerConfig({ ...BASE, CANONICAL_HOST: "PopshotPB.com" }).canonicalHost).toBe("popshotpb.com");
  });

  it.each(["https://popshotpb.com", "popshotpb.com/", "popshotpb.com:443", "localhost", "a b"])(
    "rejects %j",
    (value) => {
      expect(() => readServerConfig({ ...BASE, CANONICAL_HOST: value })).toThrow(ConfigError);
    },
  );
});
