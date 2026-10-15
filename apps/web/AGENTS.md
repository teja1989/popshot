# Web app (`apps/web`)

Next.js App Router, TypeScript strict, Tailwind, Motion. Setup, checks and configuration are in
`README.md`. The repository-wide rules are in `/AGENTS.md`.

## Where things go

- **Signed-in pages** live under `src/app/(app)/`. Its `layout.tsx` holds the one app shell
  (sign-in state, profile, switches, tab bar), so a tap swaps only the page. A page file
  stays thin: `await connection()`, check its IDs, render one view from `src/components/`.
  Only `/join` keeps its own shell. Public pages (`/privacy`, `/terms`, `/contact`, `/r/...`)
  sit outside the group.
- **Tabs:** `src/lib/nav.ts` says which tab each path belongs to. Five tabs at most
  (ADR 0006). A new page joins an existing tab; add it to `nav.test.ts`.
- **Logic** that can be tested without a browser goes in `src/lib/*.ts`, with a `*.test.ts`
  next to it. Components stay thin.
- **New IDs in addresses** are UUIDs, checked twice: in the page (`notFound()`) and in
  `src/lib/app-paths.ts`, so the proxy answers a malformed one with a real 404.

## Data

- Read with `useApiGet(path)` (`src/components/use-api.ts`). It keeps answers in memory for
  the session, per account, so a page you come back to shows at once and refreshes in the
  background. Admin paths are never kept. After a change, call `replace(data)` or `reload()`.
- Write with `apiPost`, `apiPut`, `apiPatch` and `apiDelete` (`src/lib/api-client.ts`). Show
  the API's own message on failure: it's written for people.
- Read query strings with `useSearchParams()`, never `window.location`. Prefetched pages
  render before the address bar changes.
- Feature switches: `useFeature(key, crewId)` for a crew's switch, `useYouFeature(key)` for
  a person's, `useEverywhere()` for tabs (`src/components/features.tsx`). Until the answer
  arrives, hide the feature.

## UI

- Reuse `src/components/ui/`: `buttonClass`, `Sheet` (bottom sheets: forms open here), `Fab`,
  `segmentTrack`/`segmentOption`/`segmentLink`, `Avatar`, icons.
- Colours come from the theme tokens in `globals.css`. Both themes must pass
  `theme-contrast.test.ts`. Use raw hex only where CSS variables can't reach, such as the
  share image (`opengraph-image.tsx`) and the browser theme colour.
- Motion respects reduced motion: check `useReducedMotion()` and keep the still version
  usable.
- Touch targets are at least 44px (`min-h-11`). Every control has a name a screen reader
  can read. Decorative parts are `aria-hidden`.
- Copy follows `src/lib/copy-rules.ts`. Run the copy tests after changing words.

## Security

- `src/proxy.ts` sets a per-request CSP nonce (no inline scripts, no `unsafe-inline`),
  redirects other hosts to the domain, and turns malformed IDs into 404s. Loading a new
  third-party script, image host or connection means changing `src/lib/csp.ts`. Prefer a
  server-side call through the API instead.
- Links to other sites open with `rel="noopener noreferrer"`. Nothing third-party is
  embedded.
- No secrets in the web app: everything in its config is public (see `README.md`).

## Tests

- Unit: `npm test` (Vitest).
- Smoke e2e: `npm run test:e2e`, against `e2e/stub-api.mjs`, for signed-out pages and the
  proxy.
- Full-stack e2e: `./dev/run.sh e2e` from the root (`e2e/full/`), for anything signed in.
  Each test signs in as its own made-up user, so tests don't share data.
- Use `watchProblems(page)` to fail on console errors and failed requests.
