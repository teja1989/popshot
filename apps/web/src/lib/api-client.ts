"use client";

import type { User } from "@firebase/auth";

// Calls the API through this app's own /api routes, with the user's fresh ID token.
export async function apiGet<T>(user: User, path: `/v1/${string}`): Promise<T> {
  const token = await user.getIdToken();
  const response = await fetch(`/api${path}`, {
    headers: { authorization: `Bearer ${token}`, accept: "application/json" },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Request failed (${String(response.status)})`);
  }
  return (await response.json()) as T;
}
