import { connection } from "next/server";

import { CrewView } from "@/components/crew-view";
import { ShellLoader } from "@/components/shell-loader";
import { readServerConfig } from "@/lib/config";

export default async function CrewPage() {
  await connection();
  const { firebase, authEmulatorHost } = readServerConfig();
  return (
    <ShellLoader firebase={firebase} authEmulatorHost={authEmulatorHost}>
      <CrewView />
    </ShellLoader>
  );
}
