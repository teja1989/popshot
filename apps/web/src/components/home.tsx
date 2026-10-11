"use client";

import { onAuthStateChanged, type User } from "@firebase/auth";
import { useEffect, useMemo, useState } from "react";

import { apiGet } from "@/lib/api-client";
import type { FirebaseWebConfig } from "@/lib/config";
import { getClientAuth, signInWithGoogle, signOut } from "@/lib/firebase-client";

import { LoadingScreen } from "./loading-screen";
import { Brand } from "./ui/brand";
import { buttonClass } from "./ui/button";
import { CourtArt } from "./ui/court-art";

interface Me {
  id: string;
  display_name: string;
  avatar_url: string | null;
}

type State =
  | { kind: "loading" }
  | { kind: "signed-out" }
  | { kind: "signed-in"; user: User; me: Me | null; problem: string | null };

export function Home({
  firebase,
  authEmulatorHost,
}: {
  firebase: FirebaseWebConfig;
  authEmulatorHost: string | null;
}) {
  // Browser-only: this component is loaded with ssr: false (see home-loader.tsx).
  const auth = useMemo(
    () => getClientAuth(firebase, authEmulatorHost),
    [firebase, authEmulatorHost],
  );
  const [state, setState] = useState<State>({ kind: "loading" });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    return onAuthStateChanged(auth, (user) => {
        if (!user) {
          setState({ kind: "signed-out" });
          return;
        }
        setState({ kind: "signed-in", user, me: null, problem: null });
        apiGet<Me>(user, "/v1/me")
          .then((me) => {
            setState({ kind: "signed-in", user, me, problem: null });
          })
          .catch(() => {
            setState({
              kind: "signed-in",
              user,
              me: null,
              problem: "We couldn't load your profile just now. Try again in a moment.",
            });
          });
    });
  }, [auth]);

  async function handleSignIn() {
    setBusy(true);
    setNotice(null);
    try {
      await signInWithGoogle(auth);
    } catch {
      setNotice("Sign-in didn't finish. Give it another try when you're ready.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSignOut() {
    setBusy(true);
    try {
      await signOut(auth);
    } finally {
      setBusy(false);
    }
  }

  if (state.kind === "loading") {
    return <LoadingScreen />;
  }

  if (state.kind === "signed-out") {
    return (
      <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col px-7 pt-14 pb-9">
        <Brand />
        <CourtArt className="mt-11 w-full" />
        <h1 className="mt-10 animate-rise text-[36px] leading-[1.08] font-[780] tracking-[-0.02em] [animation-delay:200ms] [font-stretch:108%]">
          Your crew&apos;s games, kept between you.
        </h1>
        <p className="mt-4 animate-rise text-[17px] leading-relaxed text-muted [animation-delay:300ms]">
          Log a game when you walk off the court. Popshot keeps the streaks, the rivalries and
          the partner you click with.
        </p>
        <div className="min-h-10 grow" />
        <button
          type="button"
          className={buttonClass("primary", "h-14 w-full")}
          onClick={() => void handleSignIn()}
          disabled={busy}
        >
          Continue with Google
          <ArrowIcon />
        </button>
        <p role="status" className="mt-3 min-h-6 text-center text-[15px] text-warn">
          {notice}
        </p>
        <p className="mt-1 flex items-center justify-center gap-2 text-sm text-muted">
          <LockIcon />
          Private by default. Only your crew sees your games.
        </p>
      </main>
    );
  }

  const name = state.me?.display_name ?? null;
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col gap-5 px-5 pt-12 pb-9">
      <header className="flex items-center justify-between">
        <Brand />
        <button
          type="button"
          className={buttonClass("quiet", "min-h-11 px-4 text-[15px]")}
          onClick={() => void handleSignOut()}
          disabled={busy}
        >
          Sign out
        </button>
      </header>

      <section
        aria-live="polite"
        className="flex animate-rise items-center gap-4 rounded-2xl border border-line bg-surface p-4"
      >
        <span
          aria-hidden="true"
          className="flex size-12 shrink-0 items-center justify-center rounded-full border-2 border-primary bg-chip text-[15px] font-extrabold"
        >
          {initials(name)}
        </span>
        <div className="min-w-0">
          <h1 className="truncate text-[26px] leading-tight font-extrabold tracking-[-0.01em] [font-stretch:110%]">
            {name ? `Hi, ${name}.` : "Hi."}
          </h1>
          {state.problem ? (
            <p className="text-[15px] text-warn">{state.problem}</p>
          ) : (
            <p className="text-[15px] text-muted">You&apos;re signed in.</p>
          )}
        </div>
      </section>

      <section className="flex animate-rise flex-col gap-3 rounded-2xl border border-line bg-surface p-5 [animation-delay:80ms]">
        <h2 className="text-xs font-bold tracking-[0.1em] text-muted uppercase">Your groups</h2>
        <CourtArt className="w-40" />
        <p className="text-[17px] leading-relaxed">
          Groups come next: start one for your crew and invite them with a single-use link.
        </p>
      </section>
    </main>
  );
}

function initials(name: string | null): string {
  if (!name) {
    return "?";
  }
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = parts.length > 1 ? [parts[0], parts[parts.length - 1]] : [name.trim()];
  return letters
    .map((part) => part?.[0] ?? "")
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function ArrowIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <path
        d="M4 9h10M10 5l4 4-4 4"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function LockIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      <rect x="2.5" y="6" width="9" height="6.5" rx="1.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M4.5 6V4.5a2.5 2.5 0 0 1 5 0V6" fill="none" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}
