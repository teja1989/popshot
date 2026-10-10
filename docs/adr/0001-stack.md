# 0001: Technology stack

- Status: accepted
- Date: 2026-10-10

## Context

Popshot starts as an app for a few friend groups and may grow into a product. It needs a web app first, phone apps later, Google sign-in, strong group privacy, and a stats engine. It will run on Google Cloud with GitHub for source and CI.

## Decision

- **Web:** Next.js with TypeScript, deployed to Cloud Run. Installable as a web app on phones before any native build.
- **API:** Python with FastAPI. Python suits the ratings and stats work, and FastAPI gives typed request validation through Pydantic.
- **Database:** PostgreSQL on Cloud SQL, chosen for Row-Level Security (see ADR 0002).
- **Sign-in:** Google Identity Platform (see ADR 0003).
- **Infrastructure:** Terraform. **CI/CD:** GitHub Actions with Workload Identity Federation.

## Consequences

- Two services means two build pipelines and an extra network hop. In exchange, the API owns every rule and every piece of data, and the web layer stays thin.
- Firestore was ruled out because it has no equivalent of Row-Level Security for this access pattern.
- A single Next.js app with no separate API would be simpler, but would put the stats engine in TypeScript and remove the database-enforced boundary between UI code and data.
