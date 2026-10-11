// The service worker: shows push notifications and opens the app when one is tapped. Served
// from the root so its scope covers the whole app. Plain JavaScript, kept small; it never
// caches pages or touches requests.

const SCRIPT = `
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch (error) {
    data = {};
  }
  const title = typeof data.title === "string" && data.title ? data.title : "Popshot";
  event.waitUntil(
    self.registration.showNotification(title, {
      body: typeof data.body === "string" ? data.body : "",
      icon: "/icons/192",
      badge: "/icons/192",
      tag: typeof data.tag === "string" ? data.tag : undefined,
      data: { url: typeof data.url === "string" ? data.url : "/" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  // Only ever open pages of this app.
  let target = new URL("/", self.location.origin);
  try {
    const wanted = new URL(event.notification.data && event.notification.data.url, self.location.origin);
    if (wanted.origin === self.location.origin) {
      target = wanted;
    }
  } catch (error) {}
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if (new URL(client.url).origin === self.location.origin && "focus" in client) {
          return client.focus().then((focused) => focused.navigate(target.href));
        }
      }
      return self.clients.openWindow(target.href);
    }),
  );
});
`;

export function GET(): Response {
  return new Response(SCRIPT, {
    headers: {
      "content-type": "text/javascript; charset=utf-8",
      // Browsers check for a new worker on each visit; don't let a cache keep an old one.
      "cache-control": "no-cache",
    },
  });
}
