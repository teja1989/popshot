"use client";

import dynamic from "next/dynamic";

import type { FirebaseWebConfig } from "@/lib/config";

import { LoadingScreen } from "./loading-screen";

// Firebase Auth needs browser storage, so the signed-in experience renders only in the
// browser. The server sends a calm placeholder with the same frame.
const Home = dynamic(() => import("@/components/home").then((m) => m.Home), {
  ssr: false,
  loading: () => <LoadingScreen />,
});

export function HomeLoader(props: {
  firebase: FirebaseWebConfig;
  authEmulatorHost: string | null;
}) {
  return <Home {...props} />;
}
