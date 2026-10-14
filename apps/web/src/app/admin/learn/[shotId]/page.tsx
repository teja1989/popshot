import { notFound } from "next/navigation";
import { connection } from "next/server";

import { AdminShotView } from "@/components/admin-learn-view";
import { ShellLoader } from "@/components/shell-loader";
import { readServerConfig } from "@/lib/config";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export default async function AdminShotPage({ params }: { params: Promise<{ shotId: string }> }) {
  await connection();
  const { shotId } = await params;
  // Only a well-formed ID reaches the API path.
  if (!UUID.test(shotId)) {
    notFound();
  }
  const { firebase, authEmulatorHost } = readServerConfig();
  return (
    <ShellLoader firebase={firebase} authEmulatorHost={authEmulatorHost}>
      <AdminShotView shotId={shotId} />
    </ShellLoader>
  );
}
