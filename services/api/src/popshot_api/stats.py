"""Head-to-head and fun stats, worked out from a group's games.

Definitions (agreed with the crew):
- Close game: won by 2 points or fewer (12-10 counts; so does 11-10 without win-by-2).
- Skunk: the losing side scores 2 or fewer in a game (11-0, 11-2, 15-1, 21-2 ...).
- Upset: a match won by the team with the lower crew points going in. The bigger the gap,
  the bigger the upset.
- Best partner and nemesis need MIN_PAIRING matches together (or against) before they
  count. Your nemesis is the opponent you've lost to most often, by share, and only if
  you've lost more than you've won against them.

Games are counted one by one for close games and skunks; everything else counts matches.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from popshot_api.rating import PlayedMatch, PlayerRating

CLOSE_MARGIN = 2
SKUNK_MAX = 2
MIN_PAIRING = 5
HIGHLIGHT_WINDOW = timedelta(days=30)

Result = Literal["W", "L"]


@dataclass(slots=True)
class Record:
    played: int = 0
    won: int = 0

    def add(self, won: bool) -> None:
        self.played += 1
        self.won += int(won)

    @property
    def share(self) -> float:
        return self.won / self.played if self.played else 0.0


@dataclass(frozen=True, slots=True)
class Upset:
    match_id: UUID
    played_at: datetime
    winners: tuple[UUID, ...]
    losers: tuple[UUID, ...]
    # How many crew points the winners were behind, going in.
    gap: float


@dataclass(slots=True)
class PersonalStats:
    matches: int = 0
    wins: int = 0
    # ("W", 3): won the last three. None before the first match.
    current_streak: tuple[Result, int] | None = None
    longest_win_streak: int = 0
    close_won: int = 0
    close_lost: int = 0
    skunks_given: int = 0
    skunks_taken: int = 0
    upset_wins: int = 0
    biggest_upset: Upset | None = None
    partners: dict[UUID, Record] = field(default_factory=dict)
    opponents: dict[UUID, Record] = field(default_factory=dict)


def in_order(matches: Iterable[PlayedMatch]) -> list[PlayedMatch]:
    """Played order, the same order crew points use."""
    return sorted(matches, key=lambda m: (m.played_at, str(m.id)))


def upset(match: PlayedMatch, pregame: Mapping[UUID, tuple[float, float]]) -> Upset | None:
    """The upset in this match, if the lower-rated team won."""
    before = pregame.get(match.id)
    if before is None:
        return None
    rating_a, rating_b = before
    a_won = match.winner == "A"
    gap = round((rating_b - rating_a) if a_won else (rating_a - rating_b), 2)
    if gap <= 0:
        return None
    winners, losers = (match.team_a, match.team_b) if a_won else (match.team_b, match.team_a)
    return Upset(match.id, match.played_at, tuple(winners), tuple(losers), gap)


def streaks(results: Iterable[Result]) -> tuple[tuple[Result, int] | None, int]:
    """(current streak, longest win streak) from results in played order."""
    current: tuple[Result, int] | None = None
    longest = 0
    for result in results:
        if current is not None and current[0] == result:
            current = (result, current[1] + 1)
        else:
            current = (result, 1)
        if result == "W":
            longest = max(longest, current[1])
    return current, longest


def personal(
    matches: Iterable[PlayedMatch], me: UUID, pregame: Mapping[UUID, tuple[float, float]]
) -> PersonalStats:
    stats = PersonalStats()
    results: list[Result] = []
    for match in in_order(matches):
        if me in match.team_a:
            mine, theirs, my_team = match.team_a, match.team_b, "A"
        elif me in match.team_b:
            mine, theirs, my_team = match.team_b, match.team_a, "B"
        else:
            continue
        won = match.winner == my_team
        stats.matches += 1
        stats.wins += int(won)
        results.append("W" if won else "L")
        for partner in mine:
            if partner != me:
                stats.partners.setdefault(partner, Record()).add(won)
        for opponent in theirs:
            stats.opponents.setdefault(opponent, Record()).add(won)

        _count_games(stats, match, my_team)

        found = upset(match, pregame) if won else None
        if found is not None:
            stats.upset_wins += 1
            if stats.biggest_upset is None or found.gap >= stats.biggest_upset.gap:
                stats.biggest_upset = found

    stats.current_streak, stats.longest_win_streak = streaks(results)
    return stats


def _count_games(stats: PersonalStats, match: PlayedMatch, my_team: str) -> None:
    """Close games and skunks, one game at a time."""
    for game in match.games:
        us, them = (game.team_a, game.team_b) if my_team == "A" else (game.team_b, game.team_a)
        if abs(us - them) <= CLOSE_MARGIN:
            if us > them:
                stats.close_won += 1
            else:
                stats.close_lost += 1
        if us > them and them <= SKUNK_MAX:
            stats.skunks_given += 1
        if them > us and us <= SKUNK_MAX:
            stats.skunks_taken += 1


def best_partner(partners: Mapping[UUID, Record]) -> tuple[UUID, Record] | None:
    """Highest win share together, over MIN_PAIRING matches; more matches breaks a tie."""
    eligible = [(pid, r) for pid, r in partners.items() if r.played >= MIN_PAIRING]
    if not eligible:
        return None
    return max(eligible, key=lambda item: (item[1].share, item[1].played, str(item[0])))


def nemesis(opponents: Mapping[UUID, Record]) -> tuple[UUID, Record] | None:
    """Lowest win share against, over MIN_PAIRING matches, with more losses than wins."""
    eligible = [
        (pid, r) for pid, r in opponents.items() if r.played >= MIN_PAIRING and r.won * 2 < r.played
    ]
    if not eligible:
        return None
    return min(eligible, key=lambda item: (item[1].share, -item[1].played, str(item[0])))


@dataclass(frozen=True, slots=True)
class Highlights:
    # (player, length): the longest win streak anyone listed has had. Ties go to whoever
    # got there most recently.
    streak: tuple[UUID, int] | None
    # (player, matches) in the last HIGHLIGHT_WINDOW.
    most_games: tuple[UUID, int] | None
    # The biggest upset in the last HIGHLIGHT_WINDOW.
    biggest_upset: Upset | None


def highlights(
    matches: Iterable[PlayedMatch],
    rated: Mapping[UUID, PlayerRating],
    pregame: Mapping[UUID, tuple[float, float]],
    listed: set[UUID],
    now: datetime,
) -> Highlights:
    since = now - HIGHLIGHT_WINDOW

    best_streak: tuple[int, datetime, str, UUID] | None = None
    for pid in listed:
        r = rated.get(pid)
        if r is None:
            continue
        run = 0
        for result, (played_at, _) in zip(r.results, r.history, strict=True):
            run = run + 1 if result == "W" else 0
            if run >= 2:
                candidate = (run, played_at, str(pid), pid)
                if best_streak is None or candidate[:3] > best_streak[:3]:
                    best_streak = candidate

    recent = [m for m in matches if m.played_at > since]
    counts: dict[UUID, int] = {}
    for match in recent:
        for pid in (*match.team_a, *match.team_b):
            if pid in listed:
                counts[pid] = counts.get(pid, 0) + 1
    most = max(counts.items(), key=lambda item: (item[1], str(item[0])), default=None)

    biggest: Upset | None = None
    for match in in_order(recent):
        found = upset(match, pregame)
        if found is not None and (biggest is None or found.gap >= biggest.gap):
            biggest = found

    return Highlights(
        streak=(best_streak[3], best_streak[0]) if best_streak else None,
        most_games=most,
        biggest_upset=biggest,
    )
