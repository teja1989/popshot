"use client";

import { useCallback, useEffect, useState } from "react";

import { cacheable, cacheKey, forget, readCache, writeCache } from "@/lib/api-cache";
import { apiGet, ApiError } from "@/lib/api-client";

import { useSignedIn } from "./auth";

export type Loadable<T> = { kind: "loading" } | { kind: "ready"; data: T } | { kind: "error"; status: number | null };

function remembered<T>(key: string, path: string): Loadable<T> {
  const hit = cacheable(path) ? readCache(key) : null;
  return hit ? { kind: "ready", data: hit.data as T } : { kind: "loading" };
}

/**
 * GETs an API path for the signed-in user; `reload` fetches it again, and `replace` swaps in
 * fresh data the caller already has (say, from a PATCH that returns the updated resource).
 *
 * A page you've opened before in this session shows its last answer straight away and
 * refreshes it in the background (lib/api-cache.ts; never for admin pages). If that refresh
 * hits a network or server blip, what's on screen stays; if the API says no (say, 404 after
 * you left a crew), the page shows that and the remembered answer is dropped.
 */
export function useApiGet<T>(path: `/v1/${string}`): {
  result: Loadable<T>;
  reload: () => void;
  replace: (data: T) => void;
} {
  const { user } = useSignedIn();
  const key = cacheKey(user.uid, path);
  const [state, setState] = useState<{ key: string; result: Loadable<T> }>(() => ({
    key,
    result: remembered<T>(key, path),
  }));
  const [version, setVersion] = useState(0);

  // Another path (or account) on the same screen: start from what we know about that one.
  let result = state.result;
  if (state.key !== key) {
    result = remembered<T>(key, path);
    setState({ key, result });
  }

  useEffect(() => {
    let current = true;
    apiGet<T>(user, path)
      .then((data) => {
        if (cacheable(path)) {
          writeCache(key, data);
        }
        if (current) {
          setState({ key, result: { kind: "ready", data } });
        }
      })
      .catch((error: unknown) => {
        const status = error instanceof ApiError ? error.status : null;
        // A clear answer from the API (gone, not yours any more) wins over what we remember;
        // a passing network or server blip doesn't.
        const definite = status !== null && status < 500;
        if (definite) {
          forget(key);
        }
        if (current) {
          setState((now) =>
            !definite && now.key === key && now.result.kind === "ready"
              ? now
              : { key, result: { kind: "error", status } },
          );
        }
      });
    return () => {
      current = false;
    };
  }, [user, path, key, version]);

  const reload = useCallback(() => {
    setVersion((v) => v + 1);
  }, []);
  const replace = useCallback(
    (data: T) => {
      if (cacheable(path)) {
        writeCache(key, data);
      }
      setState({ key, result: { kind: "ready", data } });
    },
    [key, path],
  );
  return { result, reload, replace };
}
