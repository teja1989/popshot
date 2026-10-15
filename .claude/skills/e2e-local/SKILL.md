---
name: e2e-local
description: Run Popshot's browser tests locally, against the whole stack (dev/run.sh e2e) or the smoke suite, and use them to prove a change: reproduce failures, mutation-check guards, take phone screenshots, measure taps. Use before pushing any web change and when a CI browser test fails.
---

# Browser tests, locally

## Two suites

| Suite | Command | Runs against | For |
|---|---|---|---|
| Smoke | `cd apps/web && npm run build && npm run test:e2e` | the production build and `e2e/stub-api.mjs` | signed-out pages, the landing page, the proxy and security headers |
| Full stack | `./dev/run.sh e2e` (repository root) | the production build, real API, Postgres, Auth emulator | everything signed in (`apps/web/e2e/full/`) |

Both run on two projects: `chromium` (desktop) and `mobile` (Pixel 7). A change isn't tested
until both pass. Extra arguments go to Playwright:
`./dev/run.sh e2e e2e/full/navigation.spec.ts --project=mobile -g "tabs"`.

## Needs

- Docker running (the first run builds the emulator image, a few minutes).
- `PLAYWRIGHT_CHROMIUM_EXECUTABLE`, if Playwright's own browser isn't installed.
- On failure: server logs are in `.dev/e2e-api.log`, `.dev/e2e-admin.log` and
  `.dev/e2e-web.log`; traces are in `apps/web/test-results/`
  (`npx playwright show-trace <zip>`).
- Behind a proxy that intercepts TLS, the emulator image's `npm install` fails on the
  certificate. Build it with the proxy's CA added, in a compose override passed with an
  extra `-f`. Don't commit that override.

## Writing a test

- Each test signs in as its own made-up user (`newUser("Name")`, `signIn`), so tests never
  share data and can run in parallel.
- Find things the way people do: `getByRole`, `getByLabel`, visible text. Not CSS classes.
- Call `watchProblems(page)` and end with `expect(problems).toEqual([])` to fail on console
  errors and failed requests.
- Wait for state, never for time: `await expect(...)` retries. Don't use `waitForTimeout`
  in a committed test.
- Test what must not happen too: the stranger, the removed member, the switch that's off.

## Proving a guard (mutation check)

1. Run the test: it passes.
2. Break the guard in the code (remove the check, flip the condition, keep it compiling).
3. Run the test again: it must fail, for the right reason.
4. Put the code back (keep a copy first) and check `git diff` shows nothing left over.

Do this for every permission check, limit and validation you add or change, and say so in
the PR.

## Screenshots and timings

- **Screenshots:** a throwaway spec in `e2e/full/` that sets `page.setViewportSize({ width:
  390, height: 844 })`, emulates light and dark (`page.emulateMedia({ colorScheme })`) and
  saves to a scratch folder outside the repository. Delete the spec before committing.
- **Timings:** measure in the browser with `performance.now()` around a click, and add network
  delay with a CDP session (`Network.emulateNetworkConditions`, about 150ms) to resemble a
  phone. `expect` polling rounds times to its retry steps, so it can't measure speed.
- Measure before and after on the same machine, and report both.

## When CI's browser tests fail

Reproduce with the same spec and project locally. If it passes alone but failed in the full
run, it depends on timing or load: find what it waits on rather than retrying. Only a run
that died before any test started (install, runner) is worth a plain re-run.
