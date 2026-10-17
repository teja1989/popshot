"""Crew points: a per-group rating from 2.00 to 6.00, updated after every game.

Like DUPR, it rates each game (each game of a best-of-3 counts on its own) by the share of
points won against what the ratings predicted, so beating a stronger team 11-9 earns more
than beating a weaker one 11-2, and winning closer than expected can cost a little.

- Expected share for team A: 1 / (1 + 10 ** ((rating_b - rating_a) / SPREAD)). A team's
  rating is its players' average. With SPREAD 4.7, a 1.0 gap expects about an 11-7 split.
- Each player moves by their own step size times (actual share - expected share). New
  players move faster, settling over their first STEADY_AFTER games.
- Ratings stay within MIN..MAX.

The whole history is replayed from the start whenever it's read, in played order, so a
late, edited or deleted game always leaves every rating exactly right.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

MIN, MAX = 2.0, 6.0
SPREAD = 4.7
STEP_NEW, STEP_SETTLED = 1.0, 0.3
STEADY_AFTER = 15

START = 3.0
LEVEL_START: Mapping[str, float] = {
    "beginner": 2.5,
    "intermediate": 3.25,
    "advanced": 4.0,
    "expert": 4.75,
}

# The Board.
RANKED_AFTER = 10  # games (logged matches) before you're ranked
RESTING_AFTER = timedelta(days=60)  # no games for this long: off the ranking until you play
RELIABLE_AFTER = 20  # games for full reliability, if you've played recently
FORM_LENGTH = 5

# How each crew is going, on the You page. Change in crew points can't be compared across
# crews (each crew is its own scale), but points won against what was expected can.
TREND_WINDOW = timedelta(days=30)
TREND_MIN_GAMES = 5  # logged matches in the window before we call it
TREND_EDGE = 0.02  # average share of points above (or below) expected: climbing (slipping)

Team = Literal["A", "B"]


@dataclass(frozen=True, slots=True)
class GameScore:
    team_a: int
    team_b: int


@dataclass(frozen=True, slots=True)
class PlayedMatch:
    id: UUID
    played_at: datetime
    team_a: Sequence[UUID]
    team_b: Sequence[UUID]
    games: Sequence[GameScore]

    @property
    def winner(self) -> Team:
        wins_a = sum(1 for g in self.games if g.team_a > g.team_b)
        return "A" if wins_a * 2 > len(self.games) else "B"


@dataclass(slots=True)
class PlayerRating:
    rating: float
    # Where they started: from their self-rated level, or START.
    start: float = START
    matches: int = 0
    wins: int = 0
    last_played: datetime | None = None
    # Most recent last.
    results: list[Literal["W", "L"]] = field(default_factory=list)
    # (played_at, rating after that match), oldest first.
    history: list[tuple[datetime, float]] = field(default_factory=list)
    # (played_at, share of points won minus expected, averaged over the match's games).
    edges: list[tuple[datetime, float]] = field(default_factory=list)


def expected_share(rating_a: float, rating_b: float) -> float:
    """Share of points team A is expected to win."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / SPREAD))


def step(matches_played: int) -> float:
    settled = min(matches_played, STEADY_AFTER) / STEADY_AFTER
    return STEP_NEW + (STEP_SETTLED - STEP_NEW) * settled


def clamp(value: float) -> float:
    return max(MIN, min(MAX, value))


def replay(
    matches: Iterable[PlayedMatch],
    starts: Mapping[UUID, float],
    pregame: dict[UUID, tuple[float, float]] | None = None,
    edges: dict[UUID, float] | None = None,
) -> dict[UUID, PlayerRating]:
    """Ratings for every player after all `matches`, played in time order.

    `starts` gives a player's starting rating (from a self-rated level); anyone missing
    starts at START. If `pregame` is given, it's filled with each match's team ratings
    (team A, team B) going into that match; if `edges` is, with team A's points share above
    expected in each match (team B's is the negative).
    """
    players: dict[UUID, PlayerRating] = {}

    def player(pid: UUID) -> PlayerRating:
        if pid not in players:
            first = starts.get(pid, START)
            players[pid] = PlayerRating(rating=first, start=first)
        return players[pid]

    for match in sorted(matches, key=lambda m: (m.played_at, str(m.id))):
        side_a = [player(p) for p in match.team_a]
        side_b = [player(p) for p in match.team_b]
        if pregame is not None:
            pregame[match.id] = (_average(side_a), _average(side_b))
        surprises: list[float] = []
        for game in match.games:
            total = game.team_a + game.team_b
            if total == 0:
                continue
            surprise = game.team_a / total - expected_share(_average(side_a), _average(side_b))
            surprises.append(surprise)
            # Step sizes from before this match, so game order within it doesn't matter.
            for p in side_a:
                p.rating = clamp(p.rating + step(p.matches) * surprise)
            for p in side_b:
                p.rating = clamp(p.rating - step(p.matches) * surprise)
        winner = match.winner
        edge_a = sum(surprises) / len(surprises) if surprises else 0.0
        if edges is not None:
            edges[match.id] = edge_a
        for team, side in (("A", side_a), ("B", side_b)):
            for p in side:
                won = team == winner
                p.edges.append((match.played_at, edge_a if team == "A" else -edge_a))
                p.matches += 1
                p.wins += int(won)
                p.last_played = match.played_at
                p.results.append("W" if won else "L")
                p.history.append((match.played_at, p.rating))
    return players


def _average(side: Sequence[PlayerRating]) -> float:
    return sum(p.rating for p in side) / len(side)


def reliability(rated: PlayerRating, now: datetime) -> int:
    """0-100: how settled a rating is. Grows with games, fades after a month off."""
    if rated.last_played is None:
        return 0
    amount = min(rated.matches, RELIABLE_AFTER) / RELIABLE_AFTER
    idle = (now - rated.last_played).days
    recency = 1.0 if idle <= 30 else max(0.5, 1.0 - (idle - 30) / 120)
    return round(100 * amount * recency)


def week_change(rated: PlayerRating, now: datetime) -> float | None:
    """Movement over the last 7 days, or None if they hadn't played before then."""
    week_ago = now - timedelta(days=7)
    before = [rating for at, rating in rated.history if at <= week_ago]
    if not before:
        return None
    return rated.rating - before[-1]


@dataclass(frozen=True, slots=True)
class Trend:
    games: int  # logged matches in the window
    change: float  # crew points now minus at the start of the window
    edge: float | None  # average points share above expected; None without games
    label: Literal["climbing", "steady", "slipping"] | None  # None under TREND_MIN_GAMES


def trend(rated: PlayerRating, now: datetime) -> Trend:
    """How the last TREND_WINDOW has gone in this crew."""
    since = now - TREND_WINDOW
    edges = [edge for at, edge in rated.edges if at > since]
    before = [rating for at, rating in rated.history if at <= since]
    change = rated.rating - (before[-1] if before else rated.start)
    edge = sum(edges) / len(edges) if edges else None
    label: Literal["climbing", "steady", "slipping"] | None = None
    if edge is not None and len(edges) >= TREND_MIN_GAMES:
        if edge >= TREND_EDGE:
            label = "climbing"
        elif edge <= -TREND_EDGE:
            label = "slipping"
        else:
            label = "steady"
    return Trend(games=len(edges), change=change, edge=edge, label=label)
