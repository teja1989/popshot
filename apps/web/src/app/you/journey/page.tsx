import { connection } from "next/server";

import { JourneyView } from "@/components/journey-view";
import { ShellLoader } from "@/components/shell-loader";
import { readServerConfig } from "@/lib/config";

export default async function JourneyPage() {
  await connection();
  const { firebase, authEmulatorHost } = readServerConfig();
  return (
    <ShellLoader firebase={firebase} authEmulatorHost={authEmulatorHost}>
      <JourneyView />
    </ShellLoader>
  );
}
