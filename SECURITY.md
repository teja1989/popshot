# Security

Popshot holds people's names, sign-in identities and game history, and groups are promised to be private. We treat that promise as the core feature.

## Reporting a vulnerability

Please don't open a public issue. Use GitHub's private vulnerability reporting on this repository (Security tab → "Report a vulnerability"). You'll get a reply within a few days.

## Ground rules for contributors

- Never commit secrets, keys, tokens, `.env` files or real project config. CI scans every push and pull request with gitleaks, and a local pre-commit hook does the same.
- Deployments authenticate with Workload Identity Federation. There are no long-lived service account keys anywhere.
- Every table holding group data carries a `group_id` and is protected by Postgres Row-Level Security that is enabled and forced. The API connects with a database role that cannot bypass it.
- Any change touching data access must keep the cross-group isolation test suite green and, for a new table or endpoint, extend it.
- Dependencies are watched by Dependabot, and code is scanned by CodeQL.

## Data we keep

Only what the app needs: your Google account ID, display name and avatar, the groups you belong to and the games you've played. You can export your data or delete your account. Past games from a deleted account stay as "Former player" so other members' stats don't break.
