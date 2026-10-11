# Popshot web

Next.js (App Router, TypeScript strict) app that serves the UI, handles Google sign-in, and
forwards API calls to the private API. The browser never calls the API directly.

## Setup

The easy way is `./dev/run.sh` from the repository root (see [dev/README.md](../../dev/README.md)).
It runs this app with the API and a Firebase Auth emulator. By hand:

Needs Node 24 (see `.nvmrc`).

```sh
cd apps/web
npm ci
cp .env.example .env.local   # then fill in your dev project's values
npm run dev
```

npm install scripts are off by default (npm 11). The two packages that ship one are listed as
denied in `package.json` under `allowScripts`; neither script is needed.

## Checks

The same checks CI runs:

```sh
npm audit signatures
npm audit --audit-level=moderate
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e   # set PLAYWRIGHT_CHROMIUM_EXECUTABLE if Playwright's own browser isn't installed
```

Signed-in screens are tested against the whole stack (real API, Postgres and the Firebase
Auth emulator) with `./dev/run.sh e2e` from the repository root; see
[dev/README.md](../../dev/README.md).

The end-to-end tests run the production standalone server plus `e2e/stub-api.mjs`, a stand-in
API that echoes back exactly what the web layer forwarded.

## Configuration

Read at runtime, so the same build runs in every environment.

| Variable | Required | Meaning |
|---|---|---|
| `API_BASE_URL` | yes | API origin. Must be https, except http for localhost |
| `API_AUDIENCE` | on Cloud Run | Audience for the web service's identity token to call the API |
| `FIREBASE_API_KEY` | yes | Firebase web config (public, not a secret) |
| `FIREBASE_AUTH_DOMAIN` | yes | Firebase auth domain; also allowed as a CSP `frame-src` |
| `FIREBASE_PROJECT_ID` | yes | Firebase / Identity Platform project |
| `FIREBASE_APP_ID` | yes | Firebase web app ID |
| `FIREBASE_AUTH_EMULATOR_HOST` | no | Local only: `127.0.0.1:<port>` of the Auth emulator. Refused unless the project is `demo-*` and it isn't Cloud Run |

## How requests flow

1. The browser signs in with Google through Firebase Auth and keeps the session in IndexedDB.
2. For each call it sends `Authorization: Bearer <ID token>` to this app's `/api/v1/...`.
   A bearer header, not a cookie, so classic CSRF doesn't apply; cross-site writes are refused anyway.
3. `src/app/api/[...path]/route.ts` forwards to the API with only `Authorization`, `Accept`,
   `Content-Type` (JSON only) and a validated trace header. On Cloud Run it adds
   `X-Serverless-Authorization` with the web service account's identity token, which is what
   lets Cloud Run IAM admit the call. Bodies are capped at 64 KB, calls time out after 10 s,
   redirects aren't followed, and only `content-type`, `www-authenticate` and `retry-after`
   come back.
4. The API verifies the user's token itself. The web layer is never trusted to vouch for the user.

## Security headers

- Pages get a per-request nonce CSP from `src/proxy.ts`: `script-src 'nonce-…' 'strict-dynamic'`,
  no `unsafe-inline`, `object-src 'none'`, `base-uri 'none'`, `frame-ancestors 'none'`.
- Every response gets HSTS, `nosniff`, `X-Frame-Options: DENY`, a strict referrer policy, a
  locked-down `Permissions-Policy`, and COOP `same-origin-allow-popups` (needed for the
  Google sign-in popup). See `next.config.ts`.
- Google's sign-in scripts load only when someone taps "Sign in", never on page view.

## Installable app

`src/app/manifest.ts` and the generated icons in `src/app/icons/[size]` make the app
installable from the browser. There's no service worker yet, so there's no offline support.

## Container image

```sh
docker build -t popshot-web apps/web
```

- Node 24 on Debian 13 slim, pinned by digest. Install scripts stay blocked during `npm ci`.
- Runs the Next.js standalone server as uid 10001 on port 8080. `npm` and `corepack` are removed from the runtime image.
- Works with a read-only root filesystem plus a writable `/tmp`.

CI builds it on every PR and scans it with Trivy for fixable HIGH/CRITICAL vulnerabilities and baked-in secrets.
