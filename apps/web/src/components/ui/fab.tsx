import Link from "next/link";

import { PlusIcon } from "./icons";

/**
 * Material 3's extended floating action button: the screen's main action, always in reach,
 * above the tab bar on phones. A real link, so it works from the keyboard and screen
 * readers. Leaves room at the end of the page so it never covers the last item.
 */
export function Fab({ href, label }: { href: string; label: string }) {
  return (
    <>
      <div aria-hidden="true" className="h-16" />
      <Link
        href={href}
        className="fixed right-5 bottom-24 z-20 inline-flex min-h-14 items-center gap-2 rounded-2xl bg-primary px-5 text-lead font-bold text-on-primary no-underline shadow-fab transition-[scale,filter] duration-150 ease-standard hover:brightness-95 active:scale-[0.96] lg:right-10 lg:bottom-10"
      >
        <PlusIcon />
        {label}
      </Link>
    </>
  );
}
