import { notFound } from "next/navigation";
import { connection } from "next/server";

import { EditGameView } from "@/components/log-game-view";
import { ShellLoader } from "@/components/shell-loader";
import { readServerConfig } from "@/lib/config";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export default async function EditGamePage({ params }: { params: Promise<{ id: string; matchId: string }> }) {
  await connection();
  const { id, matchId } = await params;
  // Only well-formed IDs reach the API path.
  if (!UUID.test(id) || !UUID.test(matchId)) {
    notFound();
  }
  const { firebase, authEmulatorHost } = readServerConfig();
  return (
    <ShellLoader firebase={firebase} authEmulatorHost={authEmulatorHost}>
      <EditGameView groupId={id} matchId={matchId} />
    </ShellLoader>
  );
}
