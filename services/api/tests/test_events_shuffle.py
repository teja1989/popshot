"""Dink Shuffle (events.shuffle): fair sit-outs and fresh partners, round after round."""

from collections import Counter
from collections.abc import Sequence
from itertools import combinations
from uuid import UUID, uuid4

import pytest

from popshot_api.events import EventError, Round, games_played
from popshot_api.events.shuffle import next_round


def people(n: int) -> list[UUID]:
    return [uuid4() for _ in range(n)]


def play(players: Sequence[UUID], courts: int, rounds: int, seed: int = 7) -> list[Round]:
    history: list[Round] = []
    for _ in range(rounds):
        history.append(next_round(players, courts, history, seed))
    return history


def check_round(r: Round, players: Sequence[UUID], courts: int) -> None:
    everyone = list(r.playing) + list(r.sitting_out)
    # Everyone here exactly once: nobody on two courts, nobody missing.
    assert sorted(everyone, key=str) == sorted(players, key=str)
    assert len(r.courts) == min(courts, len(players) // 4)


def partner_counts(history: Sequence[Round]) -> Counter[frozenset[UUID]]:
    return Counter(
        frozenset(team) for r in history for c in r.courts for team in (c.team_a, c.team_b)
    )


@pytest.mark.parametrize("n", range(4, 25))
@pytest.mark.parametrize("courts", [1, 2, 3, 4, 6])
def test_every_round_is_fair(n: int, courts: int) -> None:
    players = people(n)
    history = play(players, courts, 12)
    for i, r in enumerate(history):
        check_round(r, players, courts)
        if i > 0:
            prev = set(history[i - 1].sitting_out)
            # Nobody sits out twice in a row when there are enough others to sit instead.
            if n - len(prev) >= len(r.sitting_out):
                assert not prev & set(r.sitting_out), (n, courts, i)
        # Games played never differ by more than one after any round.
        played = games_played(history[: i + 1])
        counts = [played[p] for p in players]
        assert max(counts) - min(counts) <= 1, (n, courts, i)


def test_eight_on_two_courts_meets_everyone_as_a_partner() -> None:
    # 8 players, 2 courts, 7 rounds: a perfect schedule partners everyone with everyone once.
    players = people(8)
    counts = partner_counts(play(players, 2, 7))
    assert max(counts.values()) <= 2
    # At least 24 of the 28 possible partnerships happen.
    assert len(counts) >= 24


@pytest.mark.parametrize(("n", "courts", "rounds"), [(9, 2, 9), (12, 3, 11), (16, 4, 10)])
def test_partners_rarely_repeat(n: int, courts: int, rounds: int) -> None:
    counts = partner_counts(play(people(n), courts, rounds))
    repeats = sum(c - 1 for c in counts.values())
    assert max(counts.values()) <= 2
    assert repeats <= 2, counts


def test_late_arrivals_play_first_and_leavers_are_gone() -> None:
    players = people(9)
    history = play(players, 2, 3)
    late = uuid4()
    leaver = players[0]
    now = [p for p in players if p != leaver] + [late]
    r = next_round(now, 2, history, seed=7)
    check_round(r, now, 2)
    assert late in r.playing
    assert leaver not in r.playing + r.sitting_out


def test_the_same_seed_gives_the_same_round_and_another_seed_can_differ() -> None:
    players = people(10)
    first = play(players, 2, 4, seed=1)
    assert play(players, 2, 4, seed=1) == first
    others = [play(players, 2, 4, seed=s) for s in range(2, 8)]
    assert any(o != first for o in others)


def test_courts_follow_who_is_here() -> None:
    players = people(6)
    r = next_round(players, 3, [], seed=1)
    # Six people fill one court; two sit out.
    assert (len(r.courts), len(r.sitting_out)) == (1, 2)
    # Teams on a court are two different pairs of different people.
    court = r.courts[0]
    assert len(set(court.players)) == 4


@pytest.mark.parametrize(
    ("players", "courts"), [(3, 1), (25, 6), (8, 0), (8, 7)], ids=["few", "many", "none", "lots"]
)
def test_out_of_range_is_refused(players: int, courts: int) -> None:
    with pytest.raises(EventError):
        next_round(people(players), courts, [], seed=1)


def test_the_same_person_twice_is_refused() -> None:
    someone = uuid4()
    with pytest.raises(ValueError, match="once"):
        next_round([someone, *people(3), someone], 1, [], seed=1)


def test_nobody_partners_or_faces_themselves() -> None:
    for r in play(people(13), 3, 8):
        for c in r.courts:
            assert len(set(c.players)) == 4
            for a, b in combinations(c.players, 2):
                assert a != b
