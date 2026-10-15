import { notFound } from "next/navigation";
import { connection } from "next/server";

import { CrewSettingsView } from "@/components/crew-settings-view";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export default async function CrewSettingsPage({ params }: { params: Promise<{ id: string }> }) {
  await connection();
  const { id } = await params;
  // Only a well-formed ID reaches the API path.
  if (!UUID.test(id)) {
    notFound();
  }
  return <CrewSettingsView groupId={id} />;
}
