import { connection } from "next/server";

import { MoreView } from "@/components/more-view";
import { ShellLoader } from "@/components/shell-loader";
import { readServerConfig } from "@/lib/config";

export default async function MorePage() {
  await connection();
  const { firebase, authEmulatorHost } = readServerConfig();
  return (
    <ShellLoader firebase={firebase} authEmulatorHost={authEmulatorHost}>
      <MoreView />
    </ShellLoader>
  );
}
