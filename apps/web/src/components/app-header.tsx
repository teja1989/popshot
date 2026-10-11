"use client";

import { useAuth } from "./auth";
import { Brand } from "./ui/brand";
import { buttonClass } from "./ui/button";

export function AppHeader() {
  const { busy, signOut } = useAuth();
  return (
    <header className="flex items-center justify-between">
      <Brand />
      <button
        type="button"
        className={buttonClass("quiet", "min-h-11 px-4 text-[15px]")}
        onClick={() => void signOut()}
        disabled={busy}
      >
        Sign out
      </button>
    </header>
  );
}
