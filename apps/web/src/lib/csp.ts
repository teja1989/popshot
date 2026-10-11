// Content Security Policy for pages. A fresh nonce per request plus 'strict-dynamic',
// so only scripts Next.js renders with the nonce (and what they load) can run.
// Firebase sign-in needs: Google's auth endpoints (connect), the auth domain's iframe
// (frame), and Google profile pictures (img).

export function newNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return btoa(String.fromCharCode(...bytes));
}

export function buildCsp(options: {
  nonce: string;
  authDomain: string;
  dev: boolean;
  // Local development: the Firebase Auth emulator's host:port, already validated in config.
  authEmulatorHost?: string | null;
}): string {
  const { nonce, authDomain, dev, authEmulatorHost } = options;
  const emulator = authEmulatorHost ? [`http://${authEmulatorHost}`] : [];
  const directives: Record<string, string[]> = {
    "default-src": ["'self'"],
    "script-src": [
      "'self'",
      `'nonce-${nonce}'`,
      "'strict-dynamic'",
      // Ignored by browsers that support 'strict-dynamic'; a fallback for older ones.
      "https://apis.google.com",
      ...(dev ? ["'unsafe-eval'"] : []),
    ],
    // Dev only: Next's dev tooling injects inline styles without the nonce. Browsers ignore
    // 'unsafe-inline' when a nonce is present, so dev drops the nonce instead.
    "style-src": dev ? ["'self'", "'unsafe-inline'"] : ["'self'", `'nonce-${nonce}'`],
    "img-src": ["'self'", "data:", "blob:", "https://lh3.googleusercontent.com"],
    "font-src": ["'self'"],
    "connect-src": [
      "'self'",
      "https://identitytoolkit.googleapis.com",
      "https://securetoken.googleapis.com",
      ...emulator,
      ...(dev ? ["ws:"] : []),
    ],
    "frame-src": [`https://${authDomain}`, ...emulator],
    "manifest-src": ["'self'"],
    "worker-src": ["'self'"],
    "object-src": ["'none'"],
    "base-uri": ["'none'"],
    "form-action": ["'self'"],
    "frame-ancestors": ["'none'"],
  };
  const parts = Object.entries(directives).map(([name, values]) => `${name} ${values.join(" ")}`);
  if (!dev) {
    parts.push("upgrade-insecure-requests");
  }
  return parts.join("; ");
}
