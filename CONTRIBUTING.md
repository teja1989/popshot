# Contributing

Coding agents and people follow the same rules: start with [AGENTS.md](AGENTS.md) (and the
`AGENTS.md` in the area you're changing). Step-by-step playbooks for repeated tasks are in
`.claude/skills/`.

## Workflow

1. Branch from `main` (`feat/...`, `fix/...`, `chore/...`, `docs/...`). One step per pull
   request; don't base one on another that hasn't merged.
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
