# Architecture

## Overview

```
Browser ──HTTPS──▶ web (Next.js, Cloud Run, public)
                     │  forwards requests with the user's ID token
                     ▼
                   api (FastAPI, Cloud Run, internal only)
                     │  verifies token, sets app.user_id per transaction
                     ▼
                   Postgres (Cloud SQL, private IP, RLS forced)
```

Sign-in is handled by Google Identity Platform. The web app gets an ID token for the signed-in user and passes it along; the API verifies it on every request.

## Components

| Component | Tech | Responsibility |
|---|---|---|
| `apps/web` | Next.js, TypeScript | Pages, sign-in, server-side proxy to the API, security headers |
| `services/api` | Python, FastAPI, SQLAlchemy, Alembic | Data model, business rules, ratings and stats |
| Database | PostgreSQL on Cloud SQL | Storage and tenant isolation through Row-Level Security |
| `infra/terraform` | Terraform | Projects' resources, service accounts, deploy identity |

## Security model

### Trust boundaries

1. **Browser → web.** Public. The web app sets a strict Content Security Policy and other security headers. The browser never calls the API directly.
2. **web → api.** The API's Cloud Run service accepts internal traffic only, and only the web service's service account may invoke it. The user's ID token rides along and is re-verified by the API; the web layer is not trusted to vouch for the user.
3. **api → database.** The API connects as `popshot_app`, a role that owns nothing and cannot bypass RLS. Migrations run as a separate owner role.

### Group isolation

Every table holding group data has a `group_id`. RLS is enabled and forced on each of these tables. At the start of each transaction the API runs `SET LOCAL app.user_id = '<uuid>'`, and policies allow access only to rows whose group the user is an active member of. Details and alternatives considered are in [ADR 0002](adr/0002-tenant-isolation-rls.md); how it is built is in [ADR 0004](adr/0004-rls-implementation.md).

The isolation test suite proves, against a real Postgres, that a member of one group can't read, write, update or delete another group's rows, including by guessing IDs.

### Secrets

- Runtime secrets live in Secret Manager and are mounted into Cloud Run.
- GitHub Actions authenticates to Google Cloud with Workload Identity Federation; no keys are stored.
- gitleaks runs in CI and as a pre-commit hook.

## Environments

| Environment | GCP project | Deploys |
|---|---|---|
| dev | `ps-dev-xxxx` | Automatically on merge to `main` |
| prod | `ps-prod-xxxx` | Manually approved |

Project IDs are permanent in Google Cloud, so they stay neutral and short.

## Data model (initial)

- `users`: identity provider subject, display name, avatar
- `groups`: name, default format and points
- `group_members`: user, group, role (lead, co_lead, member), status
- `group_invites`: hashed token, expiry, use limit, approval required
- `players`: a person within a group, linked to a user or a guest awaiting claim
- `matches`: group, format, points-to, win-by-2, best of (1 or 3), played at, entered by, status
- `match_players`: match, player, team (A or B)
- `match_games`: match, game number, team A score, team B score
- `match_confirmations`: match, confirming user, decision
- `ratings` and `rating_history`: per group, per player
- `audit_log`: who did what, when
