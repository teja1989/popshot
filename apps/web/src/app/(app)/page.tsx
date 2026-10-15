import { connection } from "next/server";

import { HomeView } from "@/components/home-view";

export default async function Page() {
  // Render per request: the CSP nonce changes every time.
  await connection();
  return <HomeView />;
}
