import { connection } from "next/server";

import { AdminFeaturesView } from "@/components/admin-features-view";

// Linked only from the admin page. The API decides who may see it; everyone else gets "not found".
export default async function AdminFeaturesPage() {
  await connection();
  return <AdminFeaturesView />;
}
