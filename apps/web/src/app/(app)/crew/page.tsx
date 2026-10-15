import { connection } from "next/server";

import { CrewView } from "@/components/crew-view";

export default async function CrewPage() {
  await connection();
  return <CrewView />;
}
