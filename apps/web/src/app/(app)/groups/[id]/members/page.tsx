import { notFound } from "next/navigation";
import { connection } from "next/server";

import { MembersView } from "@/components/members-view";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

export default async function MembersPage({ params }: { params: Promise<{ id: string }> }) {
  await connection();
  const { id } = await params;
  if (!UUID.test(id)) {
    notFound();
  }
  return <MembersView groupId={id} />;
}
