"use client";

import { getApps, initializeApp, type FirebaseApp } from "@firebase/app";
import {
  browserPopupRedirectResolver,
  connectAuthEmulator,
  GoogleAuthProvider,
  indexedDBLocalPersistence,
  initializeAuth,
  signInWithPopup,
  signOut as firebaseSignOut,
  type Auth,
} from "@firebase/auth";

import type { FirebaseWebConfig } from "@/lib/config";

let auth: Auth | null = null;

export function getClientAuth(config: FirebaseWebConfig, emulatorHost: string | null): Auth {
  if (auth) {
    return auth;
  }
  const app: FirebaseApp = getApps()[0] ?? initializeApp(config);
  // No popupRedirectResolver here: it would load Google's sign-in scripts on every page
  // view. It's passed only when someone actually signs in.
  auth = initializeAuth(app, { persistence: indexedDBLocalPersistence });
  if (emulatorHost) {
    // Local development only; the server refuses this setting anywhere else.
    connectAuthEmulator(auth, `http://${emulatorHost}`, { disableWarnings: true });
  }
  return auth;
}

export async function signInWithGoogle(clientAuth: Auth): Promise<void> {
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: "select_account" });
  await signInWithPopup(clientAuth, provider, browserPopupRedirectResolver);
}

export async function signOut(clientAuth: Auth): Promise<void> {
  await firebaseSignOut(clientAuth);
}
