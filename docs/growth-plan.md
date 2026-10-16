# Growth plan

Status: agreed direction, 16 Oct 2026. Nothing here is built until its own PR. Paid plans stay off
during the friends trial. Prices are starting points to test, not commitments.

## The number we steer by

**Weekly active crews:** crews with at least one game logged in the last 7 days. Popshot's value
exists only when a group plays together, so a sign-up who never plays with a crew adds nothing.
Every other measure here feeds this one.

## How Popshot is different

| App | What it sells |
|---|---|
| DUPR | Your rating, rankings, competition (about $19 a year, as offered now) |
| Playtomic, PlayByPoint | Court booking for clubs |
| Score and bracket apps | Tournaments, for organisers |
| **Popshot** | **The crew itself: your friends, your games, your stories** |

"Your crew's memory." Popshot remembers every game, partnership and rivalry, tells the story after
you play, and helps the group keep playing together.

- **Friendly over competitive.** No public ranks; crew points stay inside the crew. Players who want
  a rating already use DUPR, and can use both.
- **After the game, not just the score.** Recaps, awards, partners and rivalries.
- **Built for the lead.** Every crew has one organiser. Save them time and the whole crew stays.

## The funnel

| Stage | What we measure | Today |
|---|---|---|
| Visit | Visits per door: recap link, invite link, home page, Find | Home and invite only |
| Sign up | Sign-ups, and which door they came through | Count only |
| Activate | Share of new people who play a first game with a crew within 7 days | Per crew only |
| Stay | Crews playing in week 2 and week 4 | In admin |
| Bring friends | Invites sent and recaps shared per active crew | Not yet |
| Pay | Share of active players on Plus or Crew Plus; monthly churn | Later |

The door is recorded as a single word ("recap", "invite") with the sign-up. Nothing about the
person or the link is kept.

Doors, warmest first: shared recaps, invite links, the home page (later, a nearby teaser with
counts only), and Find (built).

## Logging without stopping play

Everything depends on games being logged, and nobody wants a phone out between points. Logging
moves to after the session. Scores stay required: crew points, close games and recaps need them.

- **Log the session afterwards.** One screen after play: players come from the meetup's RSVPs, then
  a fast list of games, each a pair against a pair with a score. "Same four again" and "swap
  partners" fill the next row in one tap.
- **Voice fills a row.** "Me and Sam beat Jo and Lee, 11 to 7." The browser's speech recognition
  turns it into text (Chrome sends the audio to Google, Safari to Apple; the privacy page will say
  so), and Popshot's own rules match the names and score. The row is checked before saving. Popshot
  never receives the audio. The mic shows only where the browser supports it; typing always works.
- **One reflection for the whole session:** what went well today, and what to improve. It feeds the
  Journey check-ins.

Measured by the share of meetups with at least one game logged, and how long logging takes.

## Keeping players engaged without bothering them

The rule: Popshot speaks when something happened on court or is about to, never to fill a silence.

**Notification guardrails, built before any new nudge:**
- At most 3 pushes a week per person, apart from replies and joins they asked for.
- Quiet hours, 9 pm to 8 am in their own time zone (stored from the browser; on the privacy page;
  deleted with the account).
- No push about something they already saw in the app.
- A crew's busy week becomes one push.
- Every category can be muted (already true).

**Chosen features:**
- **Meetup RSVPs and one reminder:** in, maybe or out; a reminder the evening before. Free.
- **Partners and rivalries:** "You and Sam: 7–2 together", your closest rival this season.
- **Seasons and awards:** about 8 weeks; Most improved, Iron player, Best duo; a shareable season
  recap.

**What we won't do:** streaks you can lose, "you haven't played in a while" pushes, public
leaderboards, fake urgency, paywalls mid-game.

## Plans

Anything that brings friends in or keeps a crew playing stays free.

| | Free, always | Plus (a player) | Crew Plus (paid by the lead) |
|---|---|---|---|
| Crews, invites, Find, logging, meetups, RSVPs, courts | ✓ | ✓ | ✓ |
| Recaps and sharing | ✓ | ✓ | ✓ |
| Your stats | Last 30 days | All time, trends, partner chemistry | |
| Journey | Tip of the day | Full check-ins and picks | |
| Seasons, awards, season recap | | | ✓ for everyone in the crew |
| Lead tools: round robins, fair teams, events, Friendly Cup | | | ✓ |
| Price to test | $0 | ~$1.99 a month or $14.99 a year, 14 days free | By band, below |

Crew Plus gives crew features only, never anyone's personal Plus.

**Crew Plus is priced by active players**, meaning anyone (guests included) who played at least
one game in the season:

| Band | Active players in the season | Price to test |
|---|---|---|
| Crew | Up to 16 | $29.99 a year |
| Big crew | Up to 40 | $49.99 a year |
| Club | More than 40 | Talk to us |

- Soft, never a lockout: a crew that grows past its band keeps everything for the season; the new
  band applies at renewal.
- One free trial per crew and per account.
- Yearly at about 35–40% off monthly; cancelling takes two taps.

## Return on investment

Running costs today, from the Terraform at list prices (check the billing page for real figures):

| Item | Setup | Rough cost |
|---|---|---|
| Database | Cloud SQL `db-f1-micro`, 10 GB | ~$10–12 a month |
| Web and API | Cloud Run, one warm instance each | ~$25–50 a month |
| Admin, Gemini, Places, domain, logs | Scales to zero or capped by daily limits | A few dollars |
| **Total** | | **~$40–70 a month, about $500–850 a year** |

Assumptions: 3% of active players on Plus, 8–10% of active crews on Crew Plus (about $33 a year on
average); payment fees about 5%.

| Scale | Revenue a year | Costs a year | Result |
|---|---|---|---|
| Friends trial: 100 players, 10 crews | ~$70 | ~$600 | Loss |
| 1,000 players, 80 crews | ~$700 | ~$900 | About break-even |
| 10,000 players, 700 crews | ~$6,600 | ~$3,000 | Profit, but small |

Subscriptions pay for the servers; they don't make a business until there are tens of thousands of
players. Two levers matter more than price tuning:
1. **Clubs and venues:** leagues, ladders and court listings at $20–50 a month (the Club band).
2. **Check demand before building payments:** a counted "Plus is coming, tell me when" button.

Consumer benchmarks used, all rough: 2–5% of users pay for freemium apps, strong ones 8–15%;
health and fitness apps keep about 3–8% of people at day 30.

## Where free is enough

| Gap | Decision | Why |
|---|---|---|
| Crew Plus covers the crew, so members never buy Plus | Accept | By design: Crew Plus is crew features, Plus is personal depth |
| 30 days of stats is enough for casual players | Accept | Plus is for keen players |
| The data download has the full history | Accept | Your data is your right; it's raw rows, not insights |
| Opponents logged as guests to stay in a lower band | Close | Guests count as active players |
| Splitting a crew for cheaper bands | Not a gap | Each crew needs its own plan |
| New accounts to repeat trials | Close | One trial per crew and per account |
| Buy one season, then cancel | Accept | Awards stay; tools stop; yearly pricing is the default |
| Written recaps (Gemini) are free and cost the most | Decide later | Option: free recaps use Popshot's own words; Gemini-written ones with Crew Plus |
| Shared recaps are public by link | Accept | That's the marketing loop |

## Order of work

Each step is one or two small PRs from `main`, behind a switch, and measured before the next.

| Step | What |
|---|---|
| Done | Find: open crews near you, join, report, the open switch for leads |
| 1 | Measure (doors, activation, invites and shares; "Plus is coming" counter) and notification guardrails |
| 2 | Meetup RSVPs and the evening-before reminder |
| 3 | Log the session: scores, voice to fill a row, one reflection per session |
| 4 | Partners and rivalries |
| 5 | Seasons and awards |
| 6 | The shared-recap door, and the three ways forward after sign-up |
| 7 | Plus and Crew Plus: payments, bands, trials (only after seasons ship) |

## Parked

**Popshot at the court:** a QR sign at public courts with a digital paddle stack for open play.
Scan to join the queue, get told when you're up, games log themselves, and people who keep playing
together are offered a crew. A live board shows counts, never names. Venues could pay for it. There
is a busy open-play court nearby for a pilot.

## Still open

- Whether the full Journey check-ins move behind Plus. Anyone using them during the trial keeps
  them, and any change is announced first.
- Whether the session reflection replaces the per-game "How did it go?". Reflections already saved
  stay.
