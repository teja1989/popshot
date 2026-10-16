import type { Page } from "@playwright/test";

/** Call the API (through the web's /api proxy) as whoever is signed in on `page`. For
 *  setting things up quickly; what's under test goes through the screens. */
export async function apiAs(page: Page, method: string, path: string, body?: unknown): Promise<unknown> {
  return page.evaluate(
    async ({ method, path, body }) => {
      const token = await new Promise<string>((resolve, reject) => {
        const open = indexedDB.open("firebaseLocalStorageDb", 1);
        open.onerror = () => reject(open.error ?? new Error("indexedDB open failed"));
        open.onsuccess = () => {
          const read = open.result.transaction("firebaseLocalStorage").objectStore("firebaseLocalStorage").getAll();
          read.onsuccess = () => {
            const rows = read.result as { value: { stsTokenManager?: { accessToken?: string } } }[];
            const found = rows.find((r) => r.value.stsTokenManager?.accessToken)?.value.stsTokenManager?.accessToken;
            open.result.close();
            if (found) {
              resolve(found);
            } else {
              reject(new Error("not signed in"));
            }
          };
        };
      });
      const response = await fetch(`/api${path}`, {
        method,
        headers: { authorization: `Bearer ${token}`, "content-type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      if (!response.ok) {
        throw new Error(`${method} ${path}: ${String(response.status)} ${await response.text()}`);
      }
      return response.status === 204 ? null : ((await response.json()) as unknown);
    },
    { method, path, body },
  );
}

/** Log a singles game to 11 through the API, you against `guest` (already in the crew), and
 *  return its id. For tests whose subject isn't the log screen; that has its own tests. */
export async function logSinglesAs(
  page: Page,
  groupId: string,
  guest: string,
  [mine, theirs]: [number, number],
): Promise<string> {
  const players = (await apiAs(page, "GET", `/v1/groups/${groupId}/players`)) as {
    id: string;
    display_name: string;
    is_me: boolean;
  }[];
  const me = players.find((p) => p.is_me);
  const them = players.find((p) => p.display_name === guest);
  if (!me || !them) {
    throw new Error(`players not found: ${guest}`);
  }
  const game = (await apiAs(page, "POST", `/v1/groups/${groupId}/matches`, {
    format: "singles",
    points_to: 11,
    win_by_two: true,
    best_of: 1,
    team_a: [me.id],
    team_b: [them.id],
    games: [{ team_a: mine, team_b: theirs }],
  })) as { id: string };
  return game.id;
}
