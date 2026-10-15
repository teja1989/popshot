---
name: steward
description: How pull requests work in Popshot, from opening one to merge and deploy — CI checks and how to reproduce each locally, conventions for fixing failures and review comments, and what to tell the owner after a merge. Use when opening, driving or babysitting a PR in this repository.
---

# Driving a Popshot PR to green

The owner reviews and merges every PR, and approves every deploy. Your job is to hand over a
PR that's green, small and clearly described, and to keep it green.

## Before opening

- One step per PR, branched from the latest `main`. Never base a PR on another unmerged
  branch.
- Run the checks below for what you touched, plus a mutation check of each guard you added
  (see the `e2e-local` skill).
- Fill in `.github/pull_request_template.md`: what and why, how it was tested (with numbers),
  and what the owner should check after deploying. For infrastructure, say what the plan
  should show.

## The CI checks and how to reproduce them

| Check | Locally |
|---|---|
| Web lint, types, tests, build, e2e | `cd apps/web && npm run lint && npm run typecheck && npm test && npm run build && npm run test:e2e` |
| API lint, types, tests, audit | `cd services/api && uv run ruff format --check . && uv run ruff check . && uv run mypy && uv run pytest`, or `./dev/run.sh test` for the database tests |
| Full-stack browser tests | `./dev/run.sh e2e` |
| Terraform fmt, validate, scan | `terraform fmt -check -recursive`; `terraform init -backend=false && terraform validate` in each stack |
| Image web/api (build and scan) | the Dockerfiles in `apps/web` and `services/api` |
| Secret scan (gitleaks), Workflow lint (actionlint), Dependency review, CodeQL | read the finding; fix the cause |

## When something fails

- **Find the cause before pushing.** Reproduce it locally, fix it, show the same check
  passing. One proven push beats three guesses.
- **"Flaky" is not a cause.** If a test fails under load but passes alone, look for what it
  waits on (a cold service, a 5-second `expect`, a race with prefetching) and fix that.
- **Never skip, disable or loosen a test**, and never push an empty commit to re-run CI.
- **A failure that also happens on `main`:** say so on the PR, with the fix if you have one.
- **Merge conflicts:** merge `main` into the branch. Don't rebase a branch that's already
  been reviewed.

## Review comments

- Fix small, clear asks and say what changed.
- For a larger or design question, propose the change and let the owner decide.
- A bot's finding is a claim to check: trace whether it can really happen, then fix it, or
  explain why not.

## After merge

Tell the owner, in a few lines:
- what to check in the deploy plan (for example "the database updated in place, nothing
  replaced");
- what to check on the live site afterwards;
- any switch to turn on, and for whom first.
