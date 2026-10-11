import type { Metadata } from "next";
import { connection } from "next/server";

import { JoinView } from "@/components/join-view";
import { ShellLoader } from "@/components/shell-loader";
import { readServerConfig } from "@/lib/config";

// Link previews in chat apps fetch this page: they get a plain title and nothing about the
// group, because the token is in the fragment, which never reaches the server.
export const metadata: Metadata = {
  title: "You're invited · Popshot",
  robots: { index: false, follow: false },
};

export default async function JoinPage() {
  await connection();
  const { firebase, authEmulatorHost } = readServerConfig();
  return (
    <ShellLoader firebase={firebase} authEmulatorHost={authEmulatorHost} invited>
      <JoinView />
    </ShellLoader>
  );
}
