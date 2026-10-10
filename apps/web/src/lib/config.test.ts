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
  it.each(["http://localhost:8000", "http://127.0.0.1:4010", "https://api.example.com"])(
    "accepts %s",
    (value) => {
      expect(() => parseApiBaseUrl(value)).not.toThrow();
    },
  );

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
