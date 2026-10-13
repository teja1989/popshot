"use client";

import Link from "next/link";
import { useEffect, type ReactNode } from "react";

import { apiPost } from "@/lib/api-client";
import {
  arrivalSource,
  countVisit,
  forgetSource,
  rememberedSource,
  rememberSource,
  type Source,
  type VisitPage,
} from "@/lib/funnel";

import { useSignedIn } from "./auth";

// The browser side of lib/funnel.ts. All of it is best-effort: a blocked request or missing
// storage changes nothing for the person using Popshot.

function here(): Source | null {
  return arrivalSource(new URL(window.location.href));
}

/** Remembers where this browser first came from (a ?src= tag or an invite link). */
export function RememberArrival() {
  useEffect(() => {
    const source = here();
    if (source) {
      rememberSource(source);
    }
  }, []);
  return null;
}

/** Counts one visit to this arrival page, once per tab. */
export function CountVisit({ page }: { page: VisitPage }) {
  useEffect(() => {
    countVisit(page, here() ?? rememberedSource() ?? "direct");
  }, [page]);
  return null;
}

/** "Try Popshot" on a shared recap: counted, and tagged so the sign-up shows it came from a recap. */
export function TryPopshotLink({ className, children }: { className: string; children: ReactNode }) {
  return (
    <Link
      href="/?src=recap"
      className={className}
      onClick={() => {
        countVisit("recap_try", here() ?? "direct");
      }}
    >
      {children}
    </Link>
  );
}

/**
 * Once signed in, sends the remembered source (if any) and forgets it. The API keeps it only
 * for a brand-new account, so signing in later on an old one records nothing.
 */
export function SendSignupSource() {
  const { user } = useSignedIn();
  useEffect(() => {
    const source = rememberedSource();
    if (!source) {
      return;
    }
    apiPost(user, "/v1/me/source", { source }).then(
      () => {
        forgetSource();
      },
      () => {
        // Try again next time the app opens.
      },
    );
  }, [user]);
  return null;
}
