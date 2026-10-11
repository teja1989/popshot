"use client";

import { onAuthStateChanged, type User } from "@firebase/auth";
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { apiGet } from "@/lib/api-client";
import type { FirebaseWebConfig } from "@/lib/config";
import { getClientAuth, signInWithGoogle, signOut } from "@/lib/firebase-client";

export interface Me {
  id: string;
  display_name: string;
  avatar_url: string | null;
  // Self-rated level: where crew points start. Null when not set.
  self_level?: string | null;
}

export type AuthState =
  | { kind: "loading" }
  | { kind: "signed-out" }
  | { kind: "signed-in"; user: User; me: Me | null; problem: string | null };

interface AuthContextValue {
  state: AuthState;
  busy: boolean;
  notice: string | null;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
  // After you edit your profile, so every screen shows the new name.
  updateMe: (me: Me) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({
  firebase,
  authEmulatorHost,
  children,
}: {
  firebase: FirebaseWebConfig;
  authEmulatorHost: string | null;
  children: ReactNode;
}) {
  // Browser-only: the app shell is loaded with ssr: false.
  const auth = useMemo(
    () => getClientAuth(firebase, authEmulatorHost),
    [firebase, authEmulatorHost],
  );
  const [state, setState] = useState<AuthState>({ kind: "loading" });
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

  const value = useMemo<AuthContextValue>(
    () => ({
      state,
      busy,
      notice,
      signIn: async () => {
        setBusy(true);
        setNotice(null);
        try {
          await signInWithGoogle(auth);
        } catch {
          setNotice("Sign-in didn't finish. Give it another try when you're ready.");
        } finally {
          setBusy(false);
        }
      },
      signOut: async () => {
        setBusy(true);
        try {
          await signOut(auth);
        } finally {
          setBusy(false);
        }
      },
      updateMe: (me: Me) => {
        setState((current) => (current.kind === "signed-in" ? { ...current, me, problem: null } : current));
      },
    }),
    [auth, state, busy, notice],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return value;
}

/** For screens that only render when signed in (the app shell guarantees it). */
export function useSignedIn(): { user: User; me: Me | null; problem: string | null } {
  const { state } = useAuth();
  if (state.kind !== "signed-in") {
    throw new Error("useSignedIn must be used on a signed-in screen");
  }
  return state;
}
