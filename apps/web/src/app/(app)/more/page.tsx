import { connection } from "next/server";

import { MoreView } from "@/components/more-view";

export default async function MorePage() {
  await connection();
  return <MoreView />;
}
