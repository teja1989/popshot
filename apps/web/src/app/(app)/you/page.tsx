import { connection } from "next/server";

import { YouView } from "@/components/you-view";

export default async function YouPage() {
  await connection();
  return <YouView />;
}
