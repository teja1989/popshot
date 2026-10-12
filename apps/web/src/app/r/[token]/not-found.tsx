import Link from "next/link";
import { connection } from "next/server";

import { Brand } from "@/components/ui/brand";
import { buttonClass } from "@/components/ui/button";

export default async function SharedRecapGone() {
  // Rendered per request so its scripts get this request's CSP nonce.
  await connection();
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-md flex-col px-7 pt-14 pb-9">
      <Brand />
      <h1 className="mt-16 text-[34px] leading-[1.1] font-extrabold tracking-[-0.02em] [font-stretch:108%]">
        This recap link isn&apos;t available any more.
      </h1>
      <p className="mt-3 text-[17px] text-muted">
        Shared links last 30 days, and whoever shared it can turn it off. Ask your crew for a new one.
      </p>
      <Link className={buttonClass("primary", "mt-8 self-start")} href="/">
        Go to Popshot
      </Link>
    </main>
  );
}
