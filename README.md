# Popshot

Pickleball crew stats for the people you actually play with.

Log a game when you walk off the court, and Popshot keeps the running story of your crew: who's on a streak, who your toughest opponent is, which partner you click with, and who got skunked this week. Groups are private by default. Nobody outside a group sees anything inside it unless the group lead lets them in.

> Status: Phase 0 is done: it's deployed on Google Cloud and Google sign-in works. Phase 1 (groups, games, stats) is next.

## What it does (MVP)

- Sign in with Google
- Create private groups and invite people with expiring links (for one person or up to 10) that the lead or a co-lead approves
- Log doubles (default) or singles games after they finish; the score counts as soon as it's logged, and whoever logged it can edit it
- Group leaderboard, head-to-head records and a crew rating
- A personal view across every group you belong to, showing where you're playing your best
- Fun stats: nemesis, best partner, skunks, close-game record, upsets, streaks, iron player

See [docs/product.md](docs/product.md) for the full scope and roadmap.

## Run it locally

```sh
./dev/run.sh
```

Starts Postgres and a Firebase Auth emulator in containers, and the API and web app with live
reload, at http://127.0.0.1:3000. Nothing touches Google Cloud. See [dev/README.md](dev/README.md).

## Repository layout

```
apps/web/          Next.js web app (UI + server-side proxy to the API)
services/api/      FastAPI service (data, rules, stats)
infra/terraform/   Google Cloud infrastructure
dev/               Local development: containers and one script to run everything
docs/              Product notes, architecture and decision records
.github/           CI, security scanning, templates
```

## How it fits together

- The browser only talks to the web app.
- The web app forwards requests to the API, which runs privately on Cloud Run.
- The API verifies the user's sign-in token on every request and talks to Postgres.
- Postgres enforces group isolation itself with Row-Level Security, so a bug in application code still can't leak another group's data.

More detail in [docs/architecture.md](docs/architecture.md).

## Security

Please read [SECURITY.md](SECURITY.md). In short: never commit secrets or real config, and report issues privately.

## License

No license has been chosen yet, so all rights are reserved by the author.
