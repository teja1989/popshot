"use client";

import { onAuthStateChanged, type User } from "@firebase/auth";
import { useEffect, useMemo, useState } from "react";

import { apiGet } from "@/lib/api-client";
import type { FirebaseWebConfig } from "@/lib/config";
import { getClientAuth, signInWithGoogle, signOut } from "@/lib/firebase-client";

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

  return (
    <main className="page">
      <header className="brand">
        <span className="brand-mark" aria-hidden="true" />
        <span className="brand-name">Popshot</span>
      </header>

      <section className="card" aria-live="polite">
        {state.kind === "loading" && <p className="muted">One moment…</p>}

        {state.kind === "signed-out" && (
          <>
            <h1>Your crew&apos;s games, kept between you.</h1>
            <p className="lede">
              Log a game when you walk off the court. Popshot keeps track of streaks, rivalries
              and the partner you click with. Groups are private, always.
            </p>
            <button
              type="button"
              className="button"
              onClick={() => void handleSignIn()}
              disabled={busy}
            >
              Sign in with Google
            </button>
            {notice && <p className="notice">{notice}</p>}
          </>
        )}

        {state.kind === "signed-in" && (
          <>
            <h1>Hi{state.me ? `, ${state.me.display_name}` : ""}.</h1>
            {state.problem ? (
              <p className="notice">{state.problem}</p>
            ) : (
              <p className="lede">
                You&apos;re signed in. Groups and games are coming next, so check back soon.
              </p>
            )}
            <button
              type="button"
              className="button button-quiet"
              onClick={() => void handleSignOut()}
              disabled={busy}
            >
              Sign out
            </button>
          </>
        )}
      </section>
    </main>
  );
}
