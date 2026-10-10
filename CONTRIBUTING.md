# Contributing

## Workflow

1. Branch from `main` (`feat/...`, `fix/...`, `chore/...`).
2. Keep pull requests small and focused on one thing.
3. All checks must pass before merging: secret scan, workflow lint, CodeQL, and each app's lint, type and test jobs.
4. Changes to data access need a matching isolation test (see SECURITY.md).

## Local setup

Install [pre-commit](https://pre-commit.com) once, then enable the hooks:

```sh
pre-commit install
```

The hooks catch secrets, large files, merge-conflict markers and whitespace issues before they leave your machine.

App-specific setup lives in `apps/web/README.md` and `services/api/README.md`.

## Decisions

Significant technical decisions are recorded in `docs/adr/`. If you change one, add a new record rather than rewriting history.
