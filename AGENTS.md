# Popshot: guide for coding agents

Popshot is a friendly pickleball app for a crew of friends: log games, plan meetups, see
recaps and your own progress. No rankings, private by default. Read `docs/product.md` for the
product and `docs/architecture.md` for the system before changing either.

Each area has its own guide, read when you work there:
`apps/web/AGENTS.md`, `services/api/AGENTS.md`, `infra/terraform/AGENTS.md`.
Step-by-step playbooks for repeated tasks are in `.claude/skills/`.

## Map

| Path | What |
|---|---|
| `apps/web` | Next.js app (App Router, TypeScript strict): every screen, sign-in, and the `/api/v1/*` proxy to the API |
| `services/api` | FastAPI service and Postgres migrations (`migrations/versions/NNNN_*.py`). The admin pages are a second service from the same code (`admin_main.py`) |
| `infra/terraform` | GCP: `bootstrap`, then `prod/platform` and `prod/services` |
| `dev/run.sh` | The whole stack locally: Postgres and the Auth emulator in containers |
| `docs/adr` | Decisions. Change one by adding a new record, never by rewriting an old one |

## Commands

Run the checks CI runs before you push. Each README lists them in full:

- Web (`apps/web`): `npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, then
  `npm run test:e2e` (smoke, against a stub API). Format with Prettier, print width 120.
- API (`services/api`): `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy`,
  `uv run pytest` (the database tests need the URLs in `services/api/README.md`).
- Whole stack: `./dev/run.sh test` (API with a database, plus web unit tests) and
  `./dev/run.sh e2e` (browser tests on desktop and phone against the real API, Postgres and
  the Auth emulator; extra arguments go to Playwright).
- Infra: `terraform fmt -check -recursive` and `terraform validate` in each stack.

## Rules that always apply

**Work**
- One pull request per step, branched from `main`. Never stack a PR on another one: wait for
  the one before it to merge.
- Keep a PR to one thing. Infrastructure and app changes go in separate PRs when they can.
- Never commit secrets, keys, real config, the admin email address or personal data. The
  secret scan (gitleaks) runs on every push.
- Don't put model or AI-tool names in commit messages, code or docs.

**Data and security**
- Every table has row-level security, enabled and forced. The API connects as `popshot_app`,
  which owns nothing and can't bypass it (ADR 0002, 0004, 0005).
- Every change to data access comes with a database test proving someone else can't read or
  change it. See the `new-migration` skill.
- Writes that cross people or crews go through `SECURITY DEFINER` functions that check the
  caller themselves and pin `search_path`.
- The browser never calls the API directly, and the API never trusts the web layer about who
  the user is (trust boundaries in `docs/architecture.md`).

**Testing**
- Every guard (a permission check, a limit, a validation) gets a test, and a mutation check:
  break the guard on purpose, see that test fail, put it back.
- UI changes get end-to-end tests on both projects (desktop and phone), and phone
  screenshots in light and dark when the change is visible.
- Never skip, disable or loosen a test to get green.

**Product and words**
- Friendly words: nothing that shames, ranks or guesses someone's gender (`he`, `she`). The
  list is `apps/web/src/lib/copy-rules.ts`, enforced by the copy tests. Crew points help keep
  games even and are never a ranking.
- Don't say "AI" in the app's screens. Name the provider only in notes such as the privacy
  page. The copy tests enforce this too.
- At most five tabs, and every screen belongs to one of them (ADR 0006). A new feature joins
  an existing tab.
- Anything new and visible ships behind a feature switch (see the `feature-switch` skill).
- When a change affects what data is kept or shared, update the privacy page in the same PR.

## Commits and PRs

- Commit title: a plain sentence about what changed for people ("Play reads ?logged from the
  router"). Body: why, then what. Mention the tests.
- PRs follow `.github/pull_request_template.md`. Say how it was tested and what to check
  after deploying.
