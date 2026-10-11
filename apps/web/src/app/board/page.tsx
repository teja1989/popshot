import { connection } from "next/server";

import { BoardView } from "@/components/board-view";
import { ShellLoader } from "@/components/shell-loader";
import { readServerConfig } from "@/lib/config";

export default async function BoardPage() {
  await connection();
  const { firebase, authEmulatorHost } = readServerConfig();
  return (
    <ShellLoader firebase={firebase} authEmulatorHost={authEmulatorHost}>
      <BoardView />
    </ShellLoader>
  );
}
