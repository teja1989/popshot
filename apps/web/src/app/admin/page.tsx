import { connection } from "next/server";

import { AdminView } from "@/components/admin-view";
import { ShellLoader } from "@/components/shell-loader";
import { readServerConfig } from "@/lib/config";

// Not linked from anywhere. The API decides who may see it; everyone else gets "not found".
export default async function AdminPage() {
  await connection();
  const { firebase, authEmulatorHost } = readServerConfig();
  return (
    <ShellLoader firebase={firebase} authEmulatorHost={authEmulatorHost}>
      <AdminView />
    </ShellLoader>
  );
}
