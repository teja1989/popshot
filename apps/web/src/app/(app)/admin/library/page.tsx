import { connection } from "next/server";

import { AdminLibraryView } from "@/components/admin-library-view";

// Linked only from the admin page. The API decides who may see it; everyone else gets "not found".
export default async function AdminLibraryPage() {
  await connection();
  return <AdminLibraryView />;
}
