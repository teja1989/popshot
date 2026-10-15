import { connection } from "next/server";
import type { ReactNode } from "react";

import { ShellLoader } from "@/components/shell-loader";
import { readServerConfig } from "@/lib/config";

// Every signed-in page shares this one app shell (sign-in state, your profile, what's
// switched on, the tab bar), so moving between pages swaps only the page inside it: no
// sign-in check, profile fetch or "One moment…" on each tap. The join page keeps its own
// shell, since it greets signed-out visitors differently.
export default async function SignedInLayout({ children }: { children: ReactNode }) {
  // Render per request: the CSP nonce changes every time, and config is read at runtime.
  await connection();
  const { firebase, authEmulatorHost } = readServerConfig();
  return (
    <ShellLoader firebase={firebase} authEmulatorHost={authEmulatorHost}>
      {children}
    </ShellLoader>
  );
}
