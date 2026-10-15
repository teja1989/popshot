import { notFound } from "next/navigation";
import { connection } from "next/server";

import { NightView } from "@/components/night-view";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export default async function NightPage({ params }: { params: Promise<{ id: string; nightId: string }> }) {
  await connection();
  const { id, nightId } = await params;
  if (!UUID.test(id) || !UUID.test(nightId)) {
    notFound();
  }
  return <NightView groupId={id} nightId={nightId} />;
}
