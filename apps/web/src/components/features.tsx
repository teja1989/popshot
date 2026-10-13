"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { apiGet } from "@/lib/api-client";
import { featureOn, NO_FEATURES, REFRESH_MS, type MyFeatures } from "@/lib/features";

import { useSignedIn } from "./auth";

interface FeaturesValue {
  features: MyFeatures;
  everywhere: ReadonlySet<string>;
  // False until the first answer: a page can wait rather than say "not switched on".
  loaded: boolean;
}

const FeaturesContext = createContext<FeaturesValue>({ features: NO_FEATURES, everywhere: new Set(), loaded: false });

/**
 * What's switched on for you. Read when the app opens, whenever you come back to it, and every
 * few minutes, so an admin's change shows without a reload. Until the first answer (or if it
 * fails) nothing switchable shows: hiding is the safe default, and the API checks anyway.
 */
export function FeaturesProvider({ children }: { children: ReactNode }) {
  const { user } = useSignedIn();
  const [features, setFeatures] = useState<MyFeatures>(NO_FEATURES);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(() => {
    apiGet<MyFeatures>(user, "/v1/me/features")
      .then(setFeatures)
      .catch(() => {
        // Keep what we had: a passing network blip shouldn't hide things already shown.
      })
      .finally(() => {
        setLoaded(true);
      });
  }, [user]);

  useEffect(() => {
    load();
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        load();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    const timer = window.setInterval(load, REFRESH_MS);
    return () => {
      document.removeEventListener("visibilitychange", onVisible);
      window.clearInterval(timer);
    };
  }, [load]);

  const value = useMemo(() => ({ features, everywhere: new Set(features.everywhere), loaded }), [features, loaded]);
  return <FeaturesContext.Provider value={value}>{children}</FeaturesContext.Provider>;
}

/** Keys that are on in at least one of your crews. */
export function useEverywhere(): ReadonlySet<string> {
  return useContext(FeaturesContext).everywhere;
}

/** Whether the first answer about switches has come back (or failed). */
export function useFeaturesLoaded(): boolean {
  return useContext(FeaturesContext).loaded;
}

/** Is `key` (or, with "area.*", anything in that area) on for this crew? */
export function useFeature(key: string, crewId: string | null): boolean {
  return featureOn(useContext(FeaturesContext).features, key, crewId);
}
