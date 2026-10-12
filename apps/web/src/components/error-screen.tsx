"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import type { ErrorSource } from "@/lib/error-report";
import { newErrorRef } from "@/lib/error-report";
import { reportError } from "@/lib/report-error";

import { Brand } from "./ui/brand";
import { buttonClass } from "./ui/button";

/** Shown when a page breaks: what to do next, and a reference to quote to support. */
export function ErrorScreen({
  error,
  source,
  reset,
}: {
  error: Error & { digest?: string };
  source: ErrorSource;
  reset: () => void;
}) {
  const [ref] = useState(() => newErrorRef());
  useEffect(() => {
    reportError(error, source, { ref, digest: error.digest ?? null });
  }, [error, source, ref]);

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col px-7 pt-14 pb-9">
      <Brand />
      <h1 className="mt-16 text-[34px] leading-[1.1] font-extrabold tracking-[-0.02em] [font-stretch:108%]">
        That one went out.
      </h1>
      <p className="mt-3 text-[17px] text-muted">
        Something broke on our side. Games you&apos;ve saved are safe. Try again, and if it keeps happening, let us know.
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <button type="button" className={buttonClass("primary")} onClick={reset}>
          Try again
        </button>
        {/* A full page load: whatever broke starts fresh. */}
        <a className={buttonClass("quiet")} href="/">
          Go home
        </a>
      </div>
      <p className="mt-10 text-[15px] text-muted">
        Reference <span className="font-mono font-bold tracking-wider text-ink">{ref}</span>. Quote it on the{" "}
        <Link href="/contact" className="font-bold text-primary underline underline-offset-2">
          contact page
        </Link>{" "}
        so we can find what happened.
      </p>
    </main>
  );
}
