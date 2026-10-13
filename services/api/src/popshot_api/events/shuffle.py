"""Dink Shuffle: doubles round robin with rotating partners, one round at a time.

Each round:
1. Who sits out (events.choose_sitting_out): whoever has played most, never twice in a row
   when it can be avoided.
2. Everyone else is split into courts and teams to keep partners and opponents fresh:
   playing with the same partner again costs PARTNER_COST per earlier time, facing the same
   opponent again costs OPPONENT_COST per earlier time, and the cheapest arrangement found
   wins. Several random starts, each improved by swapping players between courts, keep it
   fast for 24 players and good enough that repeats only happen once they can't be helped.

The same players, history and seed always give the same round.
"""

import random
from collections.abc import Sequence
from itertools import combinations
from uuid import UUID

from popshot_api.events import (
    PER_COURT,
    Court,
    Round,
    choose_sitting_out,
    courts_in_use,
)

PARTNER_COST = 10
OPPONENT_COST = 1
STARTS = 24

# Players are numbered 0..n-1 (in id order) so the search can use plain integer tables.
Table = list[list[int]]
# The three ways to make two teams of four players a, b, c, d (positions 0..3).
SPLITS = (((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2)))


def _tables(index: dict[UUID, int], history: Sequence[Round]) -> tuple[Table, Table]:
    """How often each two players have partnered, and faced each other, so far."""
    n = len(index)
    partners = [[0] * n for _ in range(n)]
    opponents = [[0] * n for _ in range(n)]

    def add(table: Table, x: UUID, y: UUID) -> None:
        if x in index and y in index:
            i, j = index[x], index[y]
            table[i][j] += 1
            table[j][i] += 1

    for r in history:
        for court in r.courts:
            add(partners, *court.team_a)
            add(partners, *court.team_b)
            for a in court.team_a:
                for b in court.team_b:
                    add(opponents, a, b)
    return partners, opponents


def _split(four: Sequence[int], partners: Table, opponents: Table) -> tuple[int, int]:
    """(cost, which of SPLITS) for the cheapest way to make two teams of these four."""
    q = sorted(four)
    faced = sum(opponents[x][y] for x, y in combinations(q, 2))
    best = (0, -1)
    for k, ((i, j), (m, n)) in enumerate(SPLITS):
        teamed = partners[q[i]][q[j]] + partners[q[m]][q[n]]
        # Everyone on court faces everyone except their partner.
        cost = PARTNER_COST * teamed + OPPONENT_COST * (
            faced - opponents[q[i]][q[j]] - opponents[q[m]][q[n]]
        )
        if k == 0 or cost < best[0]:
            best = (cost, k)
    return best


def _improve(groups: list[list[int]], partners: Table, opponents: Table) -> int:
    """Swap players between courts while that makes it cheaper. Returns the total cost."""
    costs = [_split(g, partners, opponents)[0] for g in groups]
    improved = True
    while improved:
        improved = False
        for i, j in combinations(range(len(groups)), 2):
            for x in range(PER_COURT):
                for y in range(PER_COURT):
                    groups[i][x], groups[j][y] = groups[j][y], groups[i][x]
                    cost_i = _split(groups[i], partners, opponents)[0]
                    cost_j = _split(groups[j], partners, opponents)[0]
                    if cost_i + cost_j < costs[i] + costs[j]:
                        costs[i], costs[j], improved = cost_i, cost_j, True
                    else:
                        groups[i][x], groups[j][y] = groups[j][y], groups[i][x]
    return sum(costs)


def next_round(players: Sequence[UUID], courts: int, history: Sequence[Round], seed: int) -> Round:
    """The next round for everyone here now (`players`), given the rounds so far."""
    if len(set(players)) != len(players):
        raise ValueError("Each player can only be in an event once.")
    used = courts_in_use(len(players), courts)
    # Not for secrets: a seeded generator, so each round can be made again the same way.
    rng = random.Random(f"{seed}:{len(history)}")  # noqa: S311
    sitting = choose_sitting_out(players, len(players) - used * PER_COURT, history, rng)
    resting = set(sitting)
    playing = [p for p in sorted(players, key=str) if p not in resting]
    index = {p: i for i, p in enumerate(playing)}
    partners, opponents = _tables(index, history)

    best: tuple[int, list[list[int]]] | None = None
    for _ in range(STARTS):
        order = list(range(len(playing)))
        rng.shuffle(order)
        groups = [order[i * PER_COURT : (i + 1) * PER_COURT] for i in range(used)]
        cost = _improve(groups, partners, opponents)
        if best is None or cost < best[0]:
            best = (cost, [g[:] for g in groups])
        if cost == 0:
            break
    assert best is not None  # noqa: S101 - STARTS > 0
    made = []
    for group in best[1]:
        q = sorted(group)
        (i, j), (m, n) = SPLITS[_split(q, partners, opponents)[1]]
        made.append(Court((playing[q[i]], playing[q[j]]), (playing[q[m]], playing[q[n]])))
    return Round(courts=tuple(made), sitting_out=tuple(sorted(sitting, key=str)))
