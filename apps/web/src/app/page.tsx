import { connection } from "next/server";

import { HomeView } from "@/components/home-view";
import { ShellLoader } from "@/components/shell-loader";
import { readServerConfig } from "@/lib/config";

export default async function Page() {
  // Render per request: the CSP nonce changes every time, and config is read at runtime.
  await connection();
  const { firebase, authEmulatorHost } = readServerConfig();
  return (
    <ShellLoader firebase={firebase} authEmulatorHost={authEmulatorHost}>
      <HomeView />
    </ShellLoader>
  );
}
