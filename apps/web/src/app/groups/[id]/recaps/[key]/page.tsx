import { notFound } from "next/navigation";
import { connection } from "next/server";

import { RecapView } from "@/components/recap-view";
import { ShellLoader } from "@/components/shell-loader";
import { readServerConfig } from "@/lib/config";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export default async function RecapPage({ params }: { params: Promise<{ id: string; key: string }> }) {
  await connection();
  const { id, key } = await params;
  if (!UUID.test(id) || !UUID.test(key)) {
    notFound();
  }
  const { firebase, authEmulatorHost } = readServerConfig();
  return (
    <ShellLoader firebase={firebase} authEmulatorHost={authEmulatorHost}>
      <RecapView groupId={id} recapKey={key} />
    </ShellLoader>
  );
}
