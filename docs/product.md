# Product

## The idea

Most groups who play together every week never track anything, or they keep a notes app that nobody trusts. Popshot gives a crew a shared, private record of their games and turns it into friendly bragging rights: rivalries, partnerships, streaks and seasons.

There are plenty of score-keeping apps already. Popshot's angle is what happens after the score: the story of your crew, kept private to your crew.

## Principles

- **Private by default.** A group is invisible to anyone who isn't a member. No public profiles, no player search, no location sharing.
- **Fast to log.** Logging a game should take under 15 seconds, standing at the fence.
- **Fair records.** One player enters the score and the other team confirms it, so the history is something everyone agrees on.
- **Friendly, calm tone.** Playful where it fits (skunks, nemeses), never noisy. No hype, no gimmicks.

## Decisions so far

| Topic | Decision |
|---|---|
| Who it's for | The founder's own crews first, then other groups |
| Scoring | Final score entered after each game (best-of-3 supported) |
| Format | Doubles by default, singles available |
| Multiple groups | One person can be in any number of groups |
| Personal view | Shows the player's own stats per group and where they're doing best |
| Guest players | Allowed; a guest can sign up later and claim their history |
| Confirmation | Someone on the opposing team confirms; auto-confirms after 48 hours |
| Visibility | Every group member can see every member's stats (MVP) |
| Sign-in | Google first; Sign in with Apple before any iOS release |

## MVP scope (Phase 1)

- Google sign-in
- Create a group, invite with expiring links (one person or up to 10, valid 7 days), lead or co-lead approves every join
- Roles: lead, co-lead, member
- Log a game: format, points-to (11, 15, 21), win-by-2 on/off, players, scores per game
- Confirm or dispute a game
- Group leaderboard with crew rating
- Head-to-head records
- Personal multi-group dashboard
- Fun stats (see below)
- Installable web app on phones

### Fun stats available from final scores

- **Nemesis:** the player you lose to most
- **Best partner:** your strongest doubles pairing
- **Skunks:** games won or lost 11-0
- **Close games:** record in games decided by 2 points
- **Upsets:** wins against a higher-rated team
- **Streaks:** current and longest win streak
- **Iron player:** most games played in a period

Comeback and clutch stats need point-by-point scoring and wait for Phase 3.

### Comparing across groups

Crew ratings come from different player pools, so they can't be compared between groups. The personal view compares normalized measures instead: win rate, percentile rank within each group, and 30-day trend.

## Roadmap

| Phase | Scope |
|---|---|
| 0 | Repo, CI/CD, infrastructure, sign-in, isolation model and tests |
| 1 | MVP above |
| 2 | Seasons and badges, weekly digest, round-robin generator for open play |
| 3 | Live point scoring, opt-in written game recaps, native apps, Sign in with Apple |
| 4 | DUPR: confirm partner API access and terms, link DUPR IDs with each player's consent, export confirmed games |

## Open questions

- Hosting budget ceiling (Cloud SQL is the main always-on cost)
- License and whether the repo stays public
