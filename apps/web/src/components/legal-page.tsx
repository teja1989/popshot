import Link from "next/link";
import type { ReactNode } from "react";

import { isDraft, LEGAL, updatedOn } from "@/lib/legal";

import { Brand } from "./ui/brand";

// The privacy policy, terms and contact page: readable signed in or out, no app frame.

export const LEGAL_LINKS = [
  { href: "/privacy", label: "Privacy" },
  { href: "/terms", label: "Terms" },
  { href: "/contact", label: "Contact" },
] as const;

export function LegalLinks({ className = "" }: { className?: string }) {
  return (
    <nav aria-label="Legal" className={className}>
      <ul className="flex flex-wrap gap-x-5 gap-y-1">
        {LEGAL_LINKS.map((link) => (
          <li key={link.href}>
            <Link href={link.href} className="inline-flex min-h-11 items-center font-bold text-muted hover:text-ink">
              {link.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function LegalPage({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="min-h-dvh">
      <main className="mx-auto flex w-full max-w-2xl flex-col px-5 pt-8 pb-12 lg:px-8 lg:pt-12">
        <Link
          href="/"
          aria-label="Popshot home"
          className="inline-flex min-h-11 items-center self-start text-ink no-underline"
        >
          <Brand />
        </Link>
        <h1 className="mt-10 text-[34px] leading-[1.1] font-extrabold tracking-[-0.02em] [font-stretch:108%]">
          {title}
        </h1>
        <p className="mt-2 text-[15px] text-muted">Last updated {updatedOn()}</p>
        {isDraft() && (
          <p className="mt-5 rounded-2xl border border-line bg-chip p-4 text-[15px]">
            <strong>Draft.</strong> Some details here, like the company name, are placeholders and will be filled in
            soon.
          </p>
        )}
        <div className="legal mt-8 flex flex-col gap-4 text-[17px] leading-relaxed">{children}</div>
        <footer className="mt-12 border-t border-line pt-6 text-[15px]">
          <LegalLinks />
          <p className="legal mt-2 text-muted">
            {LEGAL.company} · <a href={`mailto:${LEGAL.contactEmail}`}>{LEGAL.contactEmail}</a>
          </p>
        </footer>
      </main>
    </div>
  );
}

export function H2({ children }: { children: ReactNode }) {
  return <h2 className="mt-6 text-[22px] font-extrabold">{children}</h2>;
}

export function List({ children }: { children: ReactNode }) {
  return <ul className="flex list-disc flex-col gap-2 pl-6 marker:text-muted">{children}</ul>;
}
