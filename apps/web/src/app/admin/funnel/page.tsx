import { connection } from "next/server";

import { AdminFunnelView } from "@/components/admin-funnel-view";
import { ShellLoader } from "@/components/shell-loader";
import { readServerConfig } from "@/lib/config";

// Linked only from the admin page. The API decides who may see it; everyone else gets "not found".
export default async function AdminFunnelPage() {
  await connection();
  const { firebase, authEmulatorHost } = readServerConfig();
  return (
    <ShellLoader firebase={firebase} authEmulatorHost={authEmulatorHost}>
      <AdminFunnelView />
    </ShellLoader>
  );
}
