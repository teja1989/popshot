import { connection } from "next/server";

import { SettingsView } from "@/components/settings-view";

export default async function SettingsPage() {
  await connection();
  return <SettingsView />;
}
