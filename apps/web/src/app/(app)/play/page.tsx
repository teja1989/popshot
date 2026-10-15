import { connection } from "next/server";

import { PlayView } from "@/components/games-view";

export default async function PlayPage() {
  await connection();
  return <PlayView />;
}
