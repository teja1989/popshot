"""Crew events: rounds of doubles on several courts, made one round at a time.

Each format (shuffle.py: Dink Shuffle, river.py: Ride the River) makes the next round from
who's here now and the rounds so far, so people can arrive late or leave early. Scores
become ordinary games elsewhere; nothing here touches the database.

Shared here: the shapes of a round, and who sits out when there are more people than spots.
"""

import random
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from uuid import UUID

PER_COURT = 4
MIN_PLAYERS = 4
MAX_PLAYERS = 24
MAX_COURTS = 6

Team = tuple[UUID, UUID]


@dataclass(frozen=True, slots=True)
class Court:
    team_a: Team
    team_b: Team

    @property
    def players(self) -> tuple[UUID, UUID, UUID, UUID]:
        return (*self.team_a, *self.team_b)


@dataclass(frozen=True, slots=True)
class Round:
    # Court 1 first. In Ride the River that's the top court.
    courts: tuple[Court, ...]
    sitting_out: tuple[UUID, ...]

    @property
    def playing(self) -> tuple[UUID, ...]:
        return tuple(p for court in self.courts for p in court.players)


class EventError(ValueError):
    """The round can't be made as asked (too few or too many people, no courts)."""


def courts_in_use(players: int, courts: int) -> int:
    """How many courts a round uses: as many as are free and can be filled with four."""
    if not MIN_PLAYERS <= players <= MAX_PLAYERS:
        raise EventError(f"An event needs {MIN_PLAYERS} to {MAX_PLAYERS} players.")
    if not 1 <= courts <= MAX_COURTS:
        raise EventError(f"Use 1 to {MAX_COURTS} courts.")
    return min(courts, players // PER_COURT)


def games_played(history: Iterable[Round]) -> Counter[UUID]:
    return Counter(p for r in history for p in r.playing)


def choose_sitting_out(
    players: Sequence[UUID], count: int, history: Sequence[Round], rng: random.Random
) -> list[UUID]:
    """Who sits out this round: those who've played most so far, never someone who sat out
    last round unless there's no other way. Ties are broken at random (from `rng`), so the
    same event and seed always give the same answer.

    Counting games rather than sit-outs keeps it fair for late arrivals: someone who joined
    in round 5 has played less, so they play first.
    """
    if count == 0:
        return []
    played = games_played(history)
    sat_last = set(history[-1].sitting_out) if history else set()
    order = sorted(players, key=str)
    rng.shuffle(order)
    order.sort(key=lambda p: (p in sat_last, -played[p]))
    return order[:count]
