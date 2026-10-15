import { notFound } from "next/navigation";
import { connection } from "next/server";

import { EventView } from "@/components/event-view";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export default async function EventPage({ params }: { params: Promise<{ id: string; eventId: string }> }) {
  await connection();
  const { id, eventId } = await params;
  if (!UUID.test(id) || !UUID.test(eventId)) {
    notFound();
  }
  return <EventView groupId={id} eventId={eventId} />;
}
