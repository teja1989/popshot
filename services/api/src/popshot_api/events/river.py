"""Ride the River ("up and down the river"): winners move up a court, losers move down.

Court 1 is the top court. After each round:
- the winners of court k move up to court k-1, and the losers move down to court k+1;
- the top court's winners and the bottom court's losers stay where they are;
- partners split: each court gets two pairs, and each new team takes one player from each.
A court with no result (skipped by the lead) keeps its four, with partners split.

The first round comes from a starting order (random, crew points or level: the organizer
picks, and the order itself is never shown). Players are dealt top court down, and on each
court the 1st and 4th play the 2nd and 3rd.

Sitting out works as in Dink Shuffle (events.choose_sitting_out). Someone who sits out
leaves a gap, which the first person coming back (or arriving) fills; anyone left over
joins at the bottom.
"""

import random
from collections.abc import Mapping, Sequence
from typing import Literal
from uuid import UUID

from popshot_api.events import (
    PER_COURT,
    Court,
    Round,
    choose_sitting_out,
    courts_in_use,
)

Winner = Literal["A", "B"]


def _first_order(players: Sequence[UUID], start: Sequence[UUID], rng: random.Random) -> list[UUID]:
    """The starting order, then anyone it doesn't list, in random order."""
    here = set(players)
    order = [p for p in start if p in here]
    rest = [p for p in sorted(players, key=str) if p not in set(order)]
    rng.shuffle(rest)
    return order + rest


def _moved(previous: Round, winners: Mapping[int, Winner]) -> list[UUID]:
    """Everyone who played last round, in their new slots, top court first.

    Each pair heads for a court: winners one up, losers one down, both pairs of a court with
    no result stay. Pairs are then ranked by that court (on a court: those who came down,
    then those who stayed, then those who came up) and dealt back two pairs to a court, top
    first, so every court is full even when a skipped court leaves one short. Each court's
    four are listed as [x1, y1, x2, y2] for its two pairs x and y, so pairing slots (1, 2)
    against (3, 4) splits both pairs.
    """
    last = len(previous.courts) - 1
    ranked: list[tuple[int, int, int, tuple[UUID, UUID]]] = []
    for k, court in enumerate(previous.courts):
        won = winners.get(k)
        if won is None:
            ranked += [(k, 1, k, court.team_a), (k, 1, k, court.team_b)]
            continue
        up, down = (court.team_a, court.team_b) if won == "A" else (court.team_b, court.team_a)
        ranked.append((max(k - 1, 0), 2 if k > 0 else 1, k, up))
        ranked.append((min(k + 1, last), 0 if k < last else 1, k, down))
    ranked.sort(key=lambda r: r[:3])
    pairs = [r[3] for r in ranked]
    slots: list[UUID] = []
    for (x1, x2), (y1, y2) in zip(pairs[0::2], pairs[1::2], strict=True):
        slots += [x1, y1, x2, y2]
    return slots


def next_round(  # noqa: PLR0913 - each input is needed
    players: Sequence[UUID],
    courts: int,
    history: Sequence[Round],
    *,
    winners: Mapping[int, Winner],
    start: Sequence[UUID],
    seed: int,
) -> Round:
    """The next round for everyone here now. `winners` says who won on each court of the
    last round (by court index, 0 is the top); `start` is the starting order for round 1."""
    if len(set(players)) != len(players):
        raise ValueError("Each player can only be in an event once.")
    used = courts_in_use(len(players), courts)
    # Not for secrets: a seeded generator, so each round can be made again the same way.
    rng = random.Random(f"{seed}:{len(history)}")  # noqa: S311
    here = set(players)

    if history:
        slots = [p for p in _moved(history[-1], winners) if p in here]
        on_court = set(slots)
        # Those who sat out last round first, then anyone new, in random order.
        waiting = [p for p in history[-1].sitting_out if p in here]
        new = [p for p in sorted(players, key=str) if p not in on_court and p not in waiting]
        rng.shuffle(new)
        waiting += new
    else:
        slots, waiting = [], _first_order(players, start, rng)

    sitting = choose_sitting_out(players, len(players) - used * PER_COURT, history, rng)
    leaving = set(sitting)
    coming = [p for p in waiting if p not in leaving]
    # Whoever comes back takes the place of someone who sits out; the rest join at the bottom.
    filled: list[UUID] = []
    for p in slots:
        if p not in leaving:
            filled.append(p)
        elif coming:
            filled.append(coming.pop(0))
    filled += coming

    if history:
        groups = [filled[i * PER_COURT : (i + 1) * PER_COURT] for i in range(used)]
        made = [Court((g[0], g[1]), (g[2], g[3])) for g in groups]
    else:
        groups = [filled[i * PER_COURT : (i + 1) * PER_COURT] for i in range(used)]
        made = [Court((g[0], g[3]), (g[1], g[2])) for g in groups]
    return Round(courts=tuple(made), sitting_out=tuple(sorted(sitting, key=str)))
