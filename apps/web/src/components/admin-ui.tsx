"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";

import { reauthenticate } from "@/lib/firebase-client";

import { useSignedIn } from "./auth";
import { buttonClass } from "./ui/button";

// Shared by the admin pages.

/**
 * What the API's admin gate answered: 404 for anyone who isn't an admin (shown as a plain
 * "not found", like any unknown page) and 403 for a sign-in over 12 hours old.
 */
export function AdminGate({
  status,
  onSignedIn,
  children,
}: {
  status: number | null;
  onSignedIn: () => void;
  children: ReactNode;
}) {
  if (status === 404) {
    return <NotFound />;
  }
  if (status === 403) {
    return <SignInAgain onDone={onSignedIn} />;
  }
  return <>{children}</>;
}

export function AdminMain({ children }: { children: ReactNode }) {
  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 px-5 pt-6 pb-12 lg:max-w-4xl lg:px-8 lg:pt-10">
      {children}
    </main>
  );
}

export function NotFound() {
  return (
    <main className="mx-auto flex w-full max-w-md flex-col px-5 pt-10 pb-12">
      <h1 className="text-title-lg leading-[1.1] font-extrabold">That page is out of bounds.</h1>
      <p className="mt-3 text-lead text-muted">The link may be old, or the page may have moved.</p>
      <Link className={buttonClass("primary", "mt-8 self-start")} href="/">
        Back to Popshot
      </Link>
    </main>
  );
}

export function SignInAgain({ onDone }: { onDone: () => void }) {
  const { user } = useSignedIn();
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-4 px-5 pt-10 pb-12">
      <h1 className="text-title-lg leading-tight font-extrabold">Sign in again</h1>
      <p className="text-lead text-muted">
        The admin page needs a sign-in from the last 12 hours. Sign in with the same Google account to carry on.
      </p>
      <button
        type="button"
        className={buttonClass("primary", "self-start")}
        disabled={busy}
        onClick={() => {
          setBusy(true);
          setProblem(null);
          reauthenticate(user)
            .then(onDone)
            .catch(() => {
              setProblem("That didn't finish. Use the same Google account you're signed in with.");
            })
            .finally(() => {
              setBusy(false);
            });
        }}
      >
        Sign in with Google
      </button>
      <p role="alert" className="text-body text-warn empty:hidden">
        {problem}
      </p>
    </main>
  );
}

export function Section({ title, children }: { title: string; children: ReactNode }) {
  const id = `admin-${title.toLowerCase().replace(/\W+/g, "-")}`;
  return (
    <section aria-labelledby={id} className="flex animate-rise flex-col gap-3">
      <h2 id={id} className="text-title-sm font-bold text-ink">
        {title}
      </h2>
      {children}
    </section>
  );
}

export function Stat({ label, value, note }: { label: string; value: number; note?: string }) {
  return (
    <div className="flex flex-col gap-1 rounded-3xl border border-transparent bg-surface shadow-card p-4">
      <dt className="text-small text-muted">{label}</dt>
      <dd className="text-title-lg leading-none font-extrabold tabular-nums font-numeral">{value}</dd>
      {note && <dd className="text-meta text-muted">{note}</dd>}
    </div>
  );
}

/** A table that scrolls sideways inside its card on narrow screens, never the page. */
export function Table({ label, head, rows }: { label: string; head: string[]; rows: (string | number)[][] }) {
  return (
    <div className="overflow-x-auto rounded-3xl border border-transparent bg-surface shadow-card">
      <table aria-label={label} className="w-full text-left text-small tabular-nums">
        <thead>
          <tr className="border-b border-line text-muted">
            {head.map((h) => (
              <th key={h} scope="col" className="px-3 py-2 font-bold whitespace-nowrap first:pl-4">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={String(row[0]) + String(row[1])} className="border-b border-line last:border-b-0">
              {row.map((cell, i) => (
                <td key={i} className="px-3 py-2 whitespace-nowrap first:pl-4 first:font-bold">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
