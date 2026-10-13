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
