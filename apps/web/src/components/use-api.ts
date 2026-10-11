"use client";

import { useCallback, useEffect, useState } from "react";

import { apiGet, ApiError } from "@/lib/api-client";

import { useSignedIn } from "./auth";

export type Loadable<T> =
  | { kind: "loading" }
  | { kind: "ready"; data: T }
  | { kind: "error"; status: number | null };

/**
 * GETs an API path for the signed-in user; `reload` fetches it again, and `replace` swaps in
 * fresh data the caller already has (say, from a PATCH that returns the updated resource).
 */
export function useApiGet<T>(path: `/v1/${string}`): {
  result: Loadable<T>;
  reload: () => void;
  replace: (data: T) => void;
} {
  const { user } = useSignedIn();
  const [result, setResult] = useState<Loadable<T>>({ kind: "loading" });
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let current = true;
    apiGet<T>(user, path)
      .then((data) => {
        if (current) {
          setResult({ kind: "ready", data });
        }
      })
      .catch((error: unknown) => {
        if (current) {
          setResult({ kind: "error", status: error instanceof ApiError ? error.status : null });
        }
      });
    return () => {
      current = false;
    };
  }, [user, path, version]);

  const reload = useCallback(() => {
    setVersion((v) => v + 1);
  }, []);
  const replace = useCallback((data: T) => {
    setResult({ kind: "ready", data });
  }, []);
  return { result, reload, replace };
}
