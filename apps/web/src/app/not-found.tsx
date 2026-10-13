import Link from "next/link";
import { connection } from "next/server";

import { Brand } from "@/components/ui/brand";
import { buttonClass } from "@/components/ui/button";

export default async function NotFound() {
  // Rendered per request so its scripts get this request's CSP nonce.
  await connection();
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col px-7 pt-14 pb-9">
      <Brand />
      <h1 className="mt-16 text-display-sm leading-[1.1] font-extrabold tracking-[-0.02em] font-display">
        That page is out of bounds.
      </h1>
      <p className="mt-3 text-lead text-muted">
        The link may be old, or the page may have moved.
      </p>
      <Link className={buttonClass("primary", "mt-8 self-start")} href="/">
        Back to Popshot
      </Link>
    </main>
  );
}
