"""Your week: a short, friendly look back at your own last 7 days, across your crews.

It's about you only and never compares you with anyone. A quiet week gets a warm line, not
a nudge about what you missed. Wins are mentioned when there are some; losses never on their
own. Close games count as in popshot_api.stats (decided by 2 points or fewer).

The words come from fixed rules, so the same week always reads the same way.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from popshot_api import stats
from popshot_api.focus import FOCUS_OPTIONS
from popshot_api.rating import PlayedMatch

WINDOW = timedelta(days=7)
LABELS = {o.id: o.label for o in FOCUS_OPTIONS}


@dataclass(frozen=True, slots=True)
class CrewWeek:
    """Your games in one crew this week, and who's who in it."""

    crew: str
    me: UUID
    matches: Sequence[PlayedMatch]
    names: Mapping[UUID, str]


@dataclass(slots=True)
class Week:
    games: int = 0
    wins: int = 0
    close_games: int = 0
    longest_win_streak: int = 0
    crews: list[str] = field(default_factory=list)
    # Who you partnered most this week, and in how many matches. Guests count too.
    top_partner: tuple[str, int] | None = None
    headline: str = ""
    lines: list[str] = field(default_factory=list)


def summarize(crews: Sequence[CrewWeek], improve: Sequence[str]) -> Week:
    """The week from your crews' matches in the window, and the focus areas you're working on."""
    week = Week()
    partners: Counter[str] = Counter()
    results: list[tuple[datetime, stats.Result]] = []
    for crew in crews:
        mine = stats.personal(crew.matches, crew.me, {})
        if mine.matches == 0:
            continue
        week.crews.append(crew.crew)
        week.games += mine.matches
        week.wins += mine.wins
        week.close_games += mine.close_won + mine.close_lost
        for pid, record in mine.partners.items():
            name = crew.names.get(pid)
            if name:
                partners[name] += record.played
        for match in stats.in_order(crew.matches):
            if crew.me in match.team_a or crew.me in match.team_b:
                my_team = "A" if crew.me in match.team_a else "B"
                results.append((match.played_at, "W" if match.winner == my_team else "L"))
    results.sort(key=lambda r: r[0])
    _, week.longest_win_streak = stats.streaks(r for _, r in results)
    if partners:
        name, count = sorted(partners.items(), key=lambda p: (-p[1], p[0].lower()))[0]
        week.top_partner = (name, count)
    week.headline, week.lines = _words(week, improve)
    return week


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many.format(n=n)


def _words(week: Week, improve: Sequence[str]) -> tuple[str, list[str]]:
    if week.games == 0:
        return (
            "A quiet week on court.",
            ["Rest weeks count too. Your crew will be glad to see you at the next meetup."],
        )
    headline = _plural(week.games, "One game this week.", "{n} games this week.")
    if len(week.crews) > 1:
        headline = headline[:-1] + f", across {len(week.crews)} crews."
    lines: list[str] = []
    if week.wins:
        lines.append(f"You won {week.wins} of {week.games}.")
    if week.longest_win_streak >= 2:
        lines.append(f"A {week.longest_win_streak}-game win streak in there.")
    if week.close_games:
        lines.append(
            _plural(
                week.close_games,
                "One game went down to the wire, decided by 2 points or fewer.",
                "{n} games went down to the wire, decided by 2 points or fewer.",
            )
        )
    if week.top_partner:
        name, count = week.top_partner
        lines.append(f"You partnered {name} most ({_plural(count, 'one game', '{n} games')}).")
    focus = next((LABELS[i] for i in improve if i in LABELS), None)
    if focus:
        if week.close_games:
            lines.append(
                f"You're working on {focus.lower()}: close games like those are the perfect"
                " place to try it."
            )
        else:
            lines.append(f"You're working on {focus.lower()}. Keep at it next time out.")
    if not week.wins and not week.close_games:
        lines.append("Every game is practice, and you showed up. That's the hard part.")
    return headline, lines


def in_window(matches: Sequence[PlayedMatch], now: datetime) -> list[PlayedMatch]:
    since = now - WINDOW
    return [m for m in matches if since < m.played_at <= now]
