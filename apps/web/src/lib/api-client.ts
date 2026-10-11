"use client";

import type { User } from "@firebase/auth";

// Calls the API through this app's own /api routes, with the user's fresh ID token.

export class ApiError extends Error {
  constructor(
    readonly status: number,
    // The API's own message when it gave one (always written for people to read).
    readonly detail: string | null,
  ) {
    super(detail ?? `Request failed (${String(status)})`);
  }
}

type ApiPath = `/v1/${string}`;

async function request<T>(user: User, path: ApiPath, init: RequestInit = {}): Promise<T> {
  const token = await user.getIdToken();
  const headers = new Headers(init.headers);
  headers.set("authorization", `Bearer ${token}`);
  headers.set("accept", "application/json");
  const response = await fetch(`/api${path}`, { ...init, headers, cache: "no-store" });
  if (!response.ok) {
    throw new ApiError(response.status, await readDetail(response));
  }
  return (await response.json()) as T;
}

async function readDetail(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    // FastAPI validation errors put a list here; only plain messages are shown to people.
    return typeof body.detail === "string" ? body.detail : null;
  } catch {
    return null;
  }
}

export function apiGet<T>(user: User, path: ApiPath): Promise<T> {
  return request<T>(user, path);
}

export function apiPost<T>(user: User, path: ApiPath, body: unknown): Promise<T> {
  return request<T>(user, path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
}
