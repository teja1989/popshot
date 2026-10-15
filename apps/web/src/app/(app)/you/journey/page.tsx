import { connection } from "next/server";

import { JourneyView } from "@/components/journey-view";

export default async function JourneyPage() {
  await connection();
  return <JourneyView />;
}
