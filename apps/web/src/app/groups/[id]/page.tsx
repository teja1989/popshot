import { notFound } from "next/navigation";
import { connection } from "next/server";

import { GroupView } from "@/components/group-view";
import { ShellLoader } from "@/components/shell-loader";
import { readServerConfig } from "@/lib/config";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export default async function GroupPage({ params }: { params: Promise<{ id: string }> }) {
  await connection();
  const { id } = await params;
  // Only a well-formed ID reaches the API path.
  if (!UUID.test(id)) {
    notFound();
  }
  const { firebase, authEmulatorHost } = readServerConfig();
  return (
    <ShellLoader firebase={firebase} authEmulatorHost={authEmulatorHost}>
      <GroupView groupId={id} />
    </ShellLoader>
  );
}
