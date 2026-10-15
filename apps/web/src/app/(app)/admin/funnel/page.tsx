import { connection } from "next/server";

import { AdminFunnelView } from "@/components/admin-funnel-view";

// Linked only from the admin page. The API decides who may see it; everyone else gets "not found".
export default async function AdminFunnelPage() {
  await connection();
  return <AdminFunnelView />;
}
