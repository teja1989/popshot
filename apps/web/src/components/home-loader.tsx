"use client";

import dynamic from "next/dynamic";

import type { FirebaseWebConfig } from "@/lib/config";

// Firebase Auth needs browser storage, so the signed-in experience renders only in the
// browser. The server sends a calm placeholder in the same card.
const Home = dynamic(() => import("@/components/home").then((m) => m.Home), {
  ssr: false,
  loading: () => (
    <main className="page">
      <header className="brand">
        <span className="brand-mark" aria-hidden="true" />
        <span className="brand-name">Popshot</span>
      </header>
      <section className="card">
        <p className="muted">One moment…</p>
      </section>
    </main>
  ),
});

export function HomeLoader({ firebase }: { firebase: FirebaseWebConfig }) {
  return <Home firebase={firebase} />;
}
