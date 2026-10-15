"use client";

import Link from "next/link";

import { buttonClass } from "./ui/button";

/**
 * Find: open crews near you, and later courts. Its tab shows only while the crew.open switch
 * is on (lib/nav.ts); until open crews arrive, this page says what's coming.
 */
export function FindView() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-5 px-5 pt-6 pb-12 lg:max-w-2xl lg:px-8 lg:pt-10">
      <h1 className="text-display-sm leading-tight font-extrabold tracking-[-0.02em] font-display">Find</h1>
      <section className="flex flex-col items-start gap-3 rounded-3xl border border-transparent bg-surface shadow-card p-5">
        <h2 className="text-title-sm font-extrabold">Crews near you are on their way</h2>
        <p className="text-lead leading-relaxed text-muted">
          Soon you&apos;ll find open crews that play near you, and join one with a tap. For now, a crew&apos;s lead can
          invite you.
        </p>
        <Link href="/crew" className={buttonClass("quiet")}>
          Go to your crews
        </Link>
      </section>
    </main>
  );
}
