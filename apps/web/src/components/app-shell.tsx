"use client";

import { setNonce } from "get-nonce";
import type { ReactNode } from "react";

import type { FirebaseWebConfig } from "@/lib/config";
// Catches the browser's one-time install event as early as possible.
import "@/lib/install";

import { AppFrame } from "./app-frame";
import { AuthProvider, useAuth } from "./auth";
import { FeaturesProvider } from "./features";
import { SendSignupSource } from "./funnel-tracking";
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
  invited = false,
  children,
}: {
  firebase: FirebaseWebConfig;
  authEmulatorHost: string | null;
  // An invite link: signed-out visitors are told why they're here.
  invited?: boolean;
  children: ReactNode;
}) {
  return (
    <AuthProvider firebase={firebase} authEmulatorHost={authEmulatorHost}>
      <Gate invited={invited}>{children}</Gate>
    </AuthProvider>
  );
}

function Gate({ invited, children }: { invited: boolean; children: ReactNode }) {
  const { state } = useAuth();
  if (state.kind === "loading") {
    return <LoadingScreen />;
  }
  if (state.kind === "signed-out") {
    return <SignInScreen invited={invited} />;
  }
  return (
    <FeaturesProvider>
      <AppFrame>
        <SendSignupSource />
        {children}
      </AppFrame>
    </FeaturesProvider>
  );
}
