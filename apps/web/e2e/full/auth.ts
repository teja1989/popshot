import { randomUUID } from "node:crypto";

import type { Page } from "@playwright/test";

// Signs a made-up Google user in through the Firebase Auth emulator, then hands the session
// to the app the way Firebase restores a returning user: from its IndexedDB store. The app
// itself has no test-only code path. (The real Google popup needs Google's servers; it's
// Google's code, and production sign-in is checked by hand.)

const EMULATOR = process.env.POPSHOT_E2E_EMULATOR_URL ?? "http://127.0.0.1:9099";
// Must match FIREBASE_API_KEY given to the web app by dev/run.sh.
const API_KEY = "demo-api-key";

export interface TestUser {
  name: string;
  email: string;
}

/** A user no other test (or earlier run) has used. */
export function newUser(first: string): TestUser {
  const id = randomUUID().slice(0, 8);
  return { name: `${first} Test`, email: `${first.toLowerCase()}-${id}@example.com` };
}

function b64url(value: object): string {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

interface SignInResponse {
  localId: string;
  idToken: string;
  refreshToken: string;
  expiresIn: string;
  email: string;
  displayName?: string;
}

export async function signIn(page: Page, user: TestUser): Promise<void> {
  // The emulator accepts an unsigned Google ID token in place of a real one.
  const googleToken = `${b64url({ alg: "none" })}.${b64url({
    sub: `google-${user.email}`,
    email: user.email,
    email_verified: true,
    name: user.name,
  })}.`;
  const response = await fetch(
    `${EMULATOR}/identitytoolkit.googleapis.com/v1/accounts:signInWithIdp?key=${API_KEY}`,
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        requestUri: "http://localhost",
        postBody: `id_token=${googleToken}&providerId=google.com`,
        returnSecureToken: true,
      }),
    },
  );
  if (!response.ok) {
    throw new Error(`Emulator sign-in failed: ${String(response.status)} ${await response.text()}`);
  }
  const session = (await response.json()) as SignInResponse;
  const now = Date.now();
  const stored = {
    uid: session.localId,
    email: user.email,
    emailVerified: true,
    displayName: user.name,
    isAnonymous: false,
    providerData: [
      {
        providerId: "google.com",
        uid: `google-${user.email}`,
        displayName: user.name,
        email: user.email,
        phoneNumber: null,
        photoURL: null,
      },
    ],
    stsTokenManager: {
      refreshToken: session.refreshToken,
      accessToken: session.idToken,
      expirationTime: now + Number(session.expiresIn) * 1000,
    },
    createdAt: String(now),
    lastLoginAt: String(now),
    apiKey: API_KEY,
    appName: "[DEFAULT]",
  };

  // Any page on the app's origin will do; the icon route loads no app code.
  await page.goto("/icons/192");
  await page.evaluate(
    async ({ key, value }) => {
      await new Promise<void>((resolve, reject) => {
        const open = indexedDB.open("firebaseLocalStorageDb", 1);
        open.onupgradeneeded = () => {
          open.result.createObjectStore("firebaseLocalStorage", { keyPath: "fbase_key" });
        };
        open.onerror = () => reject(open.error ?? new Error("indexedDB open failed"));
        open.onsuccess = () => {
          const tx = open.result.transaction("firebaseLocalStorage", "readwrite");
          tx.objectStore("firebaseLocalStorage").put({ fbase_key: key, value });
          tx.oncomplete = () => {
            open.result.close();
            resolve();
          };
          tx.onerror = () => reject(tx.error ?? new Error("indexedDB write failed"));
        };
      });
    },
    { key: `firebase:authUser:${API_KEY}:[DEFAULT]`, value: stored },
  );
}
