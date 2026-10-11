"use client";

import dynamic from "next/dynamic";
import type { ReactNode } from "react";

import type { FirebaseWebConfig } from "@/lib/config";

import { LoadingScreen } from "./loading-screen";

// Firebase Auth needs browser storage, so everything behind sign-in renders only in the
// browser. The server sends a calm placeholder with the same frame.
const AppShell = dynamic(() => import("./app-shell").then((m) => m.AppShell), {
  ssr: false,
  loading: () => <LoadingScreen />,
});

export function ShellLoader(props: {
  firebase: FirebaseWebConfig;
  authEmulatorHost: string | null;
  invited?: boolean;
  children: ReactNode;
}) {
  return <AppShell {...props} />;
}
