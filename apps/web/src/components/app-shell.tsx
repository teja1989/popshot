"use client";

import { setNonce } from "get-nonce";
import type { ReactNode } from "react";

import type { FirebaseWebConfig } from "@/lib/config";

import { AuthProvider, useAuth } from "./auth";
import { LoadingScreen } from "./loading-screen";
import { SignInScreen } from "./sign-in-screen";

// Radix dialogs lock page scrolling with a <style> element they add at runtime. The CSP
// only allows styles carrying this page's nonce, so hand Radix the nonce Next.js stamped on
// this page's scripts. (Browsers keep nonces readable from script, never from CSS.)
const pageNonce = document.querySelector<HTMLScriptElement>("script[nonce]")?.nonce;
if (pageNonce) {
  setNonce(pageNonce);
}

export function AppShell({
  firebase,
  authEmulatorHost,
  children,
}: {
  firebase: FirebaseWebConfig;
  authEmulatorHost: string | null;
  children: ReactNode;
}) {
  return (
    <AuthProvider firebase={firebase} authEmulatorHost={authEmulatorHost}>
      <Gate>{children}</Gate>
    </AuthProvider>
  );
}

function Gate({ children }: { children: ReactNode }) {
  const { state } = useAuth();
  if (state.kind === "loading") {
    return <LoadingScreen />;
  }
  if (state.kind === "signed-out") {
    return <SignInScreen />;
  }
  return <>{children}</>;
}
