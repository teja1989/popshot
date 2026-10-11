import { connection } from "next/server";

import { HomeLoader } from "@/components/home-loader";
import { readServerConfig } from "@/lib/config";

export default async function Page() {
  // Render per request: the CSP nonce changes every time, and config is read at runtime.
  await connection();
  const { firebase, authEmulatorHost } = readServerConfig();
  return <HomeLoader firebase={firebase} authEmulatorHost={authEmulatorHost} />;
}
