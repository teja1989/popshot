"use client";

import { useAuth } from "./auth";
import { buttonClass } from "./ui/button";

export function SignOutButton({ className = "" }: { className?: string }) {
  const { busy, signOut } = useAuth();
  return (
    <button
      type="button"
      className={buttonClass("quiet", `min-h-11 px-4 text-body ${className}`)}
      onClick={() => void signOut()}
      disabled={busy}
    >
      Sign out
    </button>
  );
}
