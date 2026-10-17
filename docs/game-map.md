# Your game map

Plan, 17 Oct 2026. Nothing here is built until its own PR. It lives on the You tab, for each
player about their own game. Nobody else sees it, and it never compares people.

## The idea

A four-box chart, the kind analysts use to compare phone makers, turned on yourself: one dot
for where your game is now, and a short trail for the weeks before. Each box suggests one
next step.

```
                 Ahead of expected
                        ▲
  Sharp, play more      │      In the groove
  ──────────────────────┼──────────────────────▶ Rhythm
  Getting going         │      Building           (games a week)
                        │  ●──●──◉ now
                 Room to grow
```

## What the axes measure

Both come from games already logged; nothing new is asked of players except a weekly goal.

| Axis | Measure | Middle line |
|---|---|---|
| **Rhythm** (left to right) | Games a week, averaged over the 28 days up to that point | Your own goal (default 2 a week, changeable on You) |
| **Form** (bottom to top) | Your share of points won minus the share your crew points expected, averaged over the same 28 days (the "edge" behind climbing / steady in `rating.py`) | As expected (0) |

- Form compares you with what was expected against those opponents, so a new player who
  beats the odds moves up; it never needs a strong player to lose.
- The vertical scale is clamped to ±0.15 so one lopsided game can't throw the dot off the
  chart; points beyond are drawn at the edge.
- With fewer than 5 games in a window, that week has no dot. With none at all: "A few more
  games and your map appears."
- The trail is the last 6 weeks, one dot a week, each over its own 28 days.

## The four boxes

| Box | Means | Next step offered |
|---|---|---|
| In the groove (top right) | Playing often, results ahead of expected | Share a recap; try a match-up you usually avoid |
| Sharp, play more (top left) | Results ahead, fewer games than your goal | This week's meetups; open crews nearby |
| Building (bottom right) | Lots of games, results catching up | Pick one skill to work on (Journey tip) |
| Getting going (bottom left) | Fewer games, results to come | Join a meetup; partner with someone new |

No box is bad. Words follow `copy-rules.ts`: no ranks, no "behind", no "worst".

## Slices

The same map, filtered. Every slice is free.

- **Crew:** one crew, or all of them.
- **Partner:** games with one partner. Shows your dot only, never theirs.
- **Format:** singles or doubles.
- **Period:** the trail covers 6 weeks, 3 months or all time.

A slice with fewer than 5 games says so instead of drawing a dot.

## Skills map (second, later)

Two other axes: steady game (dinks, resets, drops) and pressure (drives, speed-ups,
put-aways). Boxes: All-court, Attacker, The wall, Developing.

- **Free:** from your own after-game reflections ("went well" and "to work on" per skill),
  labelled "From your reflections".
- **Plus, behind the video switch:** from analysed video, once that pilot runs (see Video in
  `growth-plan.md`). This is the only paid part of the map.

## The chart

Built as inline SVG with the app's own tokens; no chart library.

| | Light | Dark |
|---|---|---|
| Now (emphasis) | `--c-primary` #1f6b5a | `--c-primary` #8bd6bf |
| Earlier weeks (de-emphasis) | #808a85 | #7a847f |

Checked with the dataviz validator on each theme's surface: the pair separates under all
three colour-blindness types (ΔE 12.6 light, 21.5 dark) and both clear 3:1 contrast. The
chroma and lightness-band checks don't apply: this is one highlight and a grey, not a set of
categories.

- **Form:** emphasis, not categorical: one series, the current dot in the accent, earlier
  weeks in grey, joined by a 2px line. Dots at least 8px with a 2px surface ring.
- **Axes and middle lines:** 1px hairlines in `--c-line`, solid. Quadrant names sit in the
  corners in muted text; boxes are never filled with colour (no red or green judgement).
- **Labels:** only the current dot is labelled ("Now"). No numbers on points.
- **Hover and focus:** each dot has a 24px target and a tooltip: the week, games a week,
  and form in words ("a bit ahead of expected") with the number. Dots are reachable by
  keyboard.
- **Table view:** "Show as a table" lists each week's games a week and form. Screen readers
  get a one-line summary: "You're in the groove: 2.5 games a week, results ahead of
  expected."
- **Motion:** the trail draws in on load, and stays still with reduced motion.
- **Size:** square, the full card width, on phones and desktop.

## Privacy

- Only you see your map; the API answers for the signed-in player only.
- The weekly goal is new personal data: owner-only, in the data download, deleted with the
  account, and named on the privacy page.

## Building it

Each step is one PR from `main`, behind the `you.map` switch.

| Step | What |
|---|---|
| M1 | API: `GET /v1/me/map` (weekly points, current box, slices by crew, partner, format, period) and the weekly goal; database and API tests, including that nobody else's games leak in |
| M2 | The map on You: chart, tooltips, table view, next steps; browser tests on desktop and phone; screenshots light and dark |
| M3 | Slices on the map |
| M4 | Skills map from reflections |
| Later | Skills map from video, with Plus |

## How we'll know it works

- More players open You each week.
- Players tap the suggested next step.
- Players who look at their map play more weeks than those who don't.

## Still open

- The default weekly goal: 2 games is a guess. Check against what crews actually play.
