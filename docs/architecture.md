# Architecture

## Overview

```
Browser ──HTTPS──▶ web (Next.js, Cloud Run, public)
                     │  forwards requests with the user's ID token
                     ├──────────────────────────────┐ /v1/admin only
                     ▼                              ▼
                   api (FastAPI, internal only)   admin-api (same image, internal only)
                     │  verifies token, sets app.user_id per transaction
                     ▼                              ▼
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
4. **The admin pages are a separate service.** `admin-api` (`popshot_api.admin_main`) serves only `/v1/admin`, with its own service account and database login. That login is the only one in `popshot_admin`, which can run the admin functions; it alone may look up sign-in accounts (emails) in Identity Platform. The API's login can't do either, and refuses to start if it could. Within the service, each request still has to come from an allowlisted email with a recent sign-in.

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
| prod | set in GitHub environment variables, not in the repo | On merge to `main`, after manual approval |

There's one environment for now. A separate dev project can be added later without changing
the stacks. Infrastructure lives in `infra/terraform` (bootstrap, then `prod/platform` and
`prod/services`); see `infra/terraform/prod/README.md`.

## Data model

The migrations are the source of truth: each file in `services/api/migrations/versions/`
starts with a docstring saying what it adds and who can see it. Every table has forced
row-level security.

- **People:** `users` (crewmates can read it, so nothing private goes here), `user_focus`,
  `user_activity`, `push_subscriptions`, `notification_settings`.
- **Crews:** `groups` (with the crew profile), `group_members` (lead, co_lead or member;
  pending, active or removed), `group_invites`, `direct_invites`, `invite_blocks`,
  `invite_code_lookups`.
- **Games:** `players` (a person within a crew, or a guest), `matches`, `match_players`,
  `match_games`, `match_confirmations`, `match_reflections` (only the author can read theirs),
  `ratings`, `rating_history`.
- **Getting on court:** `play_nights` and `play_night_rsvps` (meetups), and `events`,
  `event_players`, `event_rounds`, `event_courts`.
- **Recaps:** `recap_texts`, `recap_notifications`, `recap_shares`, `week_notifications`.
- **Your journey** (yours alone): `journey_entries`, `journey_notes`, `journey_settings`,
  `journey_checkins`.
- **Content and switches:** `content_items` and `content_hosts` (the library), `features`,
  `feature_crews`, `crew_plans`.
- **Admin and records:** `admin_views`, `admin_actions`, `audit_log`, `signup_sources`,
  `page_visits`.
