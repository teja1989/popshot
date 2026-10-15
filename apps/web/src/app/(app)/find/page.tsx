import { connection } from "next/server";

import { FindView } from "@/components/find-view";

export default async function FindPage() {
  await connection();
  return <FindView />;
}
