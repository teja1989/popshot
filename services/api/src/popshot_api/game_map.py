"""Your game map (docs/game-map.md): where your game is, for you alone.

Two measures, each over the WINDOW before a point in time:
- Rhythm: games a week (logged matches / WINDOW in weeks), set against your own goal.
- Form: your points share above what crew points expected (rating.replay's edge), averaged
  over those games. It's fair to new players: beating the odds counts, not winning most.

One point a week for the trail; a week with fewer than MIN_GAMES games has no form, so no
box. Nothing here compares people: it only ever reads one player's games.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

WINDOW = timedelta(days=28)
WEEK = timedelta(days=7)
MIN_GAMES = 5
DEFAULT_GOAL = 2
GOAL_RANGE = (1, 14)

Box = Literal["in_the_groove", "sharp_play_more", "building", "getting_going"]
Format = Literal["singles", "doubles"]


@dataclass(frozen=True, slots=True)
class MyGame:
    """One logged match, from the player's side."""

    played_at: datetime
    crew_id: UUID
    # Your points share above expected in this match (negative: below).
    edge: float
    # Your teammates' player ids in that crew (empty in singles).
    partners: frozenset[UUID]

    @property
    def format(self) -> Format:
        return "doubles" if self.partners else "singles"


@dataclass(frozen=True, slots=True)
class Point:
    ending: datetime
    games: int
    per_week: float
    # None under MIN_GAMES.
    form: float | None


def sliced(
    games: Iterable[MyGame],
    crew: UUID | None = None,
    partner: UUID | None = None,
    format: Format | None = None,
) -> list[MyGame]:
    """The games in one slice: a crew, a partner, singles or doubles (or all)."""
    return [
        g
        for g in games
        if (crew is None or g.crew_id == crew)
        and (partner is None or partner in g.partners)
        and (format is None or g.format == format)
    ]


def point(games: Sequence[MyGame], ending: datetime) -> Point:
    inside = [g for g in games if ending - WINDOW < g.played_at <= ending]
    form = sum(g.edge for g in inside) / len(inside) if len(inside) >= MIN_GAMES else None
    return Point(ending, len(inside), len(inside) / (WINDOW / WEEK), form)


def trail(games: Sequence[MyGame], now: datetime, weeks: int) -> list[Point]:
    """One point a week, oldest first, the last ending now."""
    return [point(games, now - WEEK * back) for back in range(weeks - 1, -1, -1)]


def box(at: Point, goal: int) -> Box | None:
    if at.form is None:
        return None
    ahead = at.form >= 0
    often = at.per_week >= goal
    if ahead:
        return "in_the_groove" if often else "sharp_play_more"
    return "building" if often else "getting_going"
