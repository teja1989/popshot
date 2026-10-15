// One address for the app. Firebase Hosting serves it on our domain; the same Cloud Run
// service also answers on its run.app address and Hosting's *.web.app one. A page opened on
// any of those is sent to the domain, so sign-in, push and installs all live in one place.

const LOCAL = new Set(["localhost", "127.0.0.1", "[::1]"]);

/** Where a page request should go instead, or null to serve it here. */
export function canonicalRedirect(url: URL, headers: Headers, canonicalHost: string | null): URL | null {
  if (canonicalHost === null) {
    return null;
  }
  // Behind Hosting the address the visitor used is in x-forwarded-host; directly on Cloud
  // Run it's the Host header. Either way only one value counts: the first.
  const reached = (headers.get("x-forwarded-host") ?? headers.get("host") ?? "").split(",")[0]?.trim() ?? "";
  const host = reached.toLowerCase().replace(/:\d+$/, "");
  if (host === canonicalHost || host === "" || LOCAL.has(host)) {
    return null;
  }
  return new URL(`${url.pathname}${url.search}`, `https://${canonicalHost}`);
}
