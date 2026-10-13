import { notFound } from "next/navigation";
import { connection } from "next/server";

import { EventView } from "@/components/event-view";
import { ShellLoader } from "@/components/shell-loader";
import { readServerConfig } from "@/lib/config";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export default async function EventPage({ params }: { params: Promise<{ id: string; eventId: string }> }) {
  await connection();
  const { id, eventId } = await params;
  if (!UUID.test(id) || !UUID.test(eventId)) {
    notFound();
  }
  const { firebase, authEmulatorHost } = readServerConfig();
  return (
    <ShellLoader firebase={firebase} authEmulatorHost={authEmulatorHost}>
      <EventView groupId={id} eventId={eventId} />
    </ShellLoader>
  );
}
