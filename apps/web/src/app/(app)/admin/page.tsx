import { connection } from "next/server";

import { AdminView } from "@/components/admin-view";

// Not linked from anywhere. The API decides who may see it; everyone else gets "not found".
export default async function AdminPage() {
  await connection();
  return <AdminView />;
}
